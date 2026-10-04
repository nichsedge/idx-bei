package engine

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"

	"github.com/nichsedge/idx-bei/pkg/models"
	"github.com/parquet-go/parquet-go"
)

var (
	alphaCacheLock sync.RWMutex
	alphaCache     *models.NetworkAlphaData
	alphaCacheMtime int64
)

// LoadDashboardData loads and caches data/network_alpha_data.json.
func LoadDashboardData(dataDir string) (*models.NetworkAlphaData, error) {
	filePath := filepath.Join(dataDir, "network_alpha_data.json")
	stat, err := os.Stat(filePath)
	if err != nil {
		return &models.NetworkAlphaData{Companies: []models.Company{}}, nil
	}

	alphaCacheLock.RLock()
	if alphaCache != nil && alphaCacheMtime == stat.ModTime().UnixNano() {
		defer alphaCacheLock.RUnlock()
		return alphaCache, nil
	}
	alphaCacheLock.RUnlock()

	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read network_alpha_data.json: %w", err)
	}

	var res models.NetworkAlphaData
	if err := json.Unmarshal(data, &res); err != nil {
		return nil, fmt.Errorf("failed to parse network_alpha_data.json: %w", err)
	}

	// Compute compounder and forensic fields if missing
	for i := range res.Companies {
		enrichCompanyForensics(&res.Companies[i])
	}

	alphaCacheLock.Lock()
	alphaCache = &res
	alphaCacheMtime = stat.ModTime().UnixNano()
	alphaCacheLock.Unlock()

	return &res, nil
}

func enrichCompanyForensics(c *models.Company) {
	if c.CompounderScore > 0 {
		return
	}
	score := 0.0
	switch v := c.Score.(type) {
	case float64:
		score = v
	case map[string]any:
		if tot, ok := v["total"].(float64); ok {
			score = tot
		}
	}
	if score <= 0 {
		score = 50.0
		if c.ROE > 15.0 {
			score += 15.0
		} else if c.ROE > 10.0 {
			score += 8.0
		}
		if c.NPM > 10.0 {
			score += 10.0
		}
		if c.DERatio > 0 && c.DERatio < 1.5 {
			score += 10.0
		}
		if c.PriceBV > 0 && c.PriceBV < 2.0 {
			score += 10.0
		}
	}
	c.CompounderScore = score

	// Value trap check: anomalous NPM (>85% on non-financials) or negative equity
	if (c.NPM > 85.0 && !strings.Contains(strings.ToLower(c.Sector), "financial")) || c.Equity < 0 {
		c.IsValueTrap = true
	}

	if c.CompounderScore >= 70.0 && !c.IsValueTrap {
		c.DCAVerdict = "PRIME_DCA"
	} else if c.CompounderScore >= 55.0 {
		c.DCAVerdict = "ACCUMULATE"
	} else {
		c.DCAVerdict = "WATCH"
	}

	if c.PriceBV > 0 && c.PriceBV < 1.0 {
		c.ValuationStatus = "SECTOR_UNDERVALUED"
	} else {
		c.ValuationStatus = "FAIR_VALUED"
	}
}

// GetCompounderScreen filters and ranks companies by compounder score.
func GetCompounderScreen(dataDir string, minScore float64, excludeTraps bool, category string, limit int) ([]models.Company, error) {
	dash, err := LoadDashboardData(dataDir)
	if err != nil {
		return nil, err
	}

	var results []models.Company
	for _, c := range dash.Companies {
		if excludeTraps && c.IsValueTrap {
			continue
		}
		if c.CompounderScore < minScore {
			continue
		}
		if category == "prime_dca" && c.DCAVerdict != "PRIME_DCA" {
			continue
		}
		if category == "sector_value" && c.ValuationStatus != "SECTOR_UNDERVALUED" {
			continue
		}
		results = append(results, c)
	}

	sort.Slice(results, func(i, j int) bool {
		return results[i].CompounderScore > results[j].CompounderScore
	})

	if limit > 0 && len(results) > limit {
		results = results[:limit]
	}
	return results, nil
}

// GetPeers finds companies in the same sector or industry.
func GetPeers(dataDir, ticker string) ([]models.Company, error) {
	dash, err := LoadDashboardData(dataDir)
	if err != nil {
		return nil, err
	}

	ticker = strings.ToUpper(ticker)
	var target *models.Company
	for i := range dash.Companies {
		if dash.Companies[i].Code == ticker {
			target = &dash.Companies[i]
			break
		}
	}
	if target == nil {
		return nil, fmt.Errorf("ticker '%s' not found", ticker)
	}

	var peers []models.Company
	for _, c := range dash.Companies {
		if c.Code != ticker && (c.Sector == target.Sector || c.Industry == target.Industry) {
			peers = append(peers, c)
		}
	}
	return peers, nil
}

// LoadStockParquetRows reads historical stock summary rows for a specific ticker.
func LoadStockParquetRows(dataDir, ticker string) ([]models.ParquetStockRow, error) {
	stockDir := filepath.Join(dataDir, "timeseries", "stock_summary")
	ticker = strings.ToUpper(ticker)

	var files []string
	_ = filepath.Walk(stockDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		if strings.HasSuffix(info.Name(), ".parquet") {
			files = append(files, path)
		}
		return nil
	})

	sort.Strings(files)

	var allRows []models.ParquetStockRow

	for _, fPath := range files {
		f, err := os.Open(fPath)
		if err != nil {
			continue
		}
		stat, err := f.Stat()
		if err != nil {
			f.Close()
			continue
		}

		pr, err := parquet.OpenFile(f, stat.Size())
		if err != nil {
			f.Close()
			continue
		}

		reader := parquet.NewGenericReader[models.ParquetStockRow](pr)
		rows := make([]models.ParquetStockRow, 256)
		for {
			n, err := reader.Read(rows)
			for i := 0; i < n; i++ {
				if rows[i].StockCode == ticker {
					allRows = append(allRows, rows[i])
				}
			}
			if err != nil {
				if err == io.EOF {
					break
				}
				break
			}
		}
		f.Close()
	}

	sort.Slice(allRows, func(i, j int) bool {
		return allRows[i].Date < allRows[j].Date
	})

	return allRows, nil
}

// GetStockData returns OHLCV records with computed technical indicators (RSI14, EMA20/50/200, Bollinger Bands, ATR14).
func GetStockData(dataDir, ticker string, limit int) ([]models.StockRecord, *models.StockRecord, error) {
	ticker = strings.ToUpper(ticker)
	rows, err := LoadStockParquetRows(dataDir, ticker)
	if err != nil || len(rows) == 0 {
		return nil, nil, fmt.Errorf("ticker '%s' not found or has no trading history", ticker)
	}

	records := make([]models.StockRecord, len(rows))
	for i, r := range rows {
		openVal := r.OpenPrice
		if openVal == 0 {
			openVal = r.Close
		}
		highVal := r.High
		if highVal == 0 {
			highVal = r.Close
		}
		lowVal := r.Low
		if lowVal == 0 {
			lowVal = r.Close
		}

		netFlow := r.ForeignBuy - r.ForeignSell

		records[i] = models.StockRecord{
			Date:             r.Date,
			Time:             r.Date,
			StockCode:        r.StockCode,
			StockName:        r.StockName,
			Open:             openVal,
			High:             highVal,
			Low:              lowVal,
			Close:            r.Close,
			Volume:           r.Volume,
			Value:            r.Value,
			Frequency:        r.Frequency,
			NetForeignFlow:   netFlow,
			ForeignBuy:       r.ForeignBuy,
			ForeignSell:      r.ForeignSell,
			NonRegularVolume: r.NonRegularVolume,
			NonRegularValue:  r.NonRegularValue,
		}
	}

	ComputeTechnicalIndicators(records)

	if limit > 0 && len(records) > limit {
		records = records[len(records)-limit:]
	}

	var latest *models.StockRecord
	if len(records) > 0 {
		latest = &records[len(records)-1]
	}

	return records, latest, nil
}

// ComputeTechnicalIndicators mutates records in-place with RSI, EMA, Bollinger Bands, and ATR.
func ComputeTechnicalIndicators(records []models.StockRecord) {
	n := len(records)
	if n == 0 {
		return
	}

	// 1. EMA 20, 50, 200
	computeEMA(records, 20, func(r *models.StockRecord, v float64) { r.EMA20 = &v })
	computeEMA(records, 50, func(r *models.StockRecord, v float64) { r.EMA50 = &v })
	computeEMA(records, 200, func(r *models.StockRecord, v float64) { r.EMA200 = &v })

	// 2. Bollinger Bands (20 periods, 2.0 std dev)
	computeBollinger(records, 20, 2.0)

	// 3. RSI 14
	computeRSI(records, 14)

	// 4. ATR 14
	computeATR(records, 14)
}

func computeEMA(records []models.StockRecord, period int, assign func(*models.StockRecord, float64)) {
	n := len(records)
	if n < period {
		return
	}
	k := 2.0 / float64(period+1)
	sum := 0.0
	for i := 0; i < period; i++ {
		sum += records[i].Close
	}
	ema := sum / float64(period)
	assign(&records[period-1], math.Round(ema*100)/100)

	for i := period; i < n; i++ {
		ema = (records[i].Close * k) + (ema * (1.0 - k))
		assign(&records[i], math.Round(ema*100)/100)
	}
}

func computeBollinger(records []models.StockRecord, period int, numStd float64) {
	n := len(records)
	if n < period {
		return
	}
	for i := period - 1; i < n; i++ {
		sum := 0.0
		for j := i - period + 1; j <= i; j++ {
			sum += records[j].Close
		}
		mean := sum / float64(period)

		variance := 0.0
		for j := i - period + 1; j <= i; j++ {
			diff := records[j].Close - mean
			variance += diff * diff
		}
		stdDev := math.Sqrt(variance / float64(period))

		upper := math.Round((mean+numStd*stdDev)*100) / 100
		mid := math.Round(mean*100) / 100
		lower := math.Round((mean-numStd*stdDev)*100) / 100

		records[i].BBUpper = &upper
		records[i].BBMid = &mid
		records[i].BBLower = &lower
	}
}

func computeRSI(records []models.StockRecord, period int) {
	n := len(records)
	if n <= period {
		return
	}

	gains := make([]float64, n)
	losses := make([]float64, n)
	for i := 1; i < n; i++ {
		change := records[i].Close - records[i-1].Close
		if change > 0 {
			gains[i] = change
		} else {
			losses[i] = -change
		}
	}

	avgGain := 0.0
	avgLoss := 0.0
	for i := 1; i <= period; i++ {
		avgGain += gains[i]
		avgLoss += losses[i]
	}
	avgGain /= float64(period)
	avgLoss /= float64(period)

	var rsi float64
	if avgLoss == 0 {
		rsi = 100.0
	} else {
		rs := avgGain / avgLoss
		rsi = 100.0 - (100.0 / (1.0 + rs))
	}
	roundedRSI := math.Round(rsi*100) / 100
	records[period].RSI14 = &roundedRSI

	for i := period + 1; i < n; i++ {
		avgGain = (avgGain*float64(period-1) + gains[i]) / float64(period)
		avgLoss = (avgLoss*float64(period-1) + losses[i]) / float64(period)

		if avgLoss == 0 {
			rsi = 100.0
		} else {
			rs := avgGain / avgLoss
			rsi = 100.0 - (100.0 / (1.0 + rs))
		}
		r := math.Round(rsi*100) / 100
		records[i].RSI14 = &r
	}
}

func computeATR(records []models.StockRecord, period int) {
	n := len(records)
	if n <= period {
		return
	}
	tr := make([]float64, n)
	for i := 1; i < n; i++ {
		h := records[i].High
		l := records[i].Low
		prevC := records[i-1].Close
		hl := h - l
		hc := math.Abs(h - prevC)
		lc := math.Abs(l - prevC)
		tr[i] = math.Max(hl, math.Max(hc, lc))
	}

	atr := 0.0
	for i := 1; i <= period; i++ {
		atr += tr[i]
	}
	atr /= float64(period)
	roundedATR := math.Round(atr*100) / 100
	records[period].ATR14 = &roundedATR

	for i := period + 1; i < n; i++ {
		atr = (atr*float64(period-1) + tr[i]) / float64(period)
		r := math.Round(atr*100) / 100
		records[i].ATR14 = &r
	}
}
