package engine

import (
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"

	"github.com/nichsedge/idx-bei/pkg/models"
)

// StealthAccumulationRecord highlights quiet institutional accumulation.
type StealthAccumulationRecord struct {
	StockCode          string  `json:"stock_code"`
	CompanyName        string  `json:"company_name"`
	ClosePrice         float64 `json:"close_price"`
	PriceChange20dPct  float64 `json:"price_change_20d_pct"`
	NetForeignFlow20d  float64 `json:"net_foreign_flow_20d"`
	Turnover20d        float64 `json:"turnover_20d"`
	FlowIntensityPct   float64 `json:"flow_intensity_pct"`
	DCAVerdict         string  `json:"dca_verdict"`
	CompounderScore    float64 `json:"compounder_score"`
}

// ForeignFlowRank contains top net foreign flow accumulation/distribution.
type ForeignFlowRank struct {
	StockCode         string  `json:"stock_code"`
	CompanyName       string  `json:"company_name"`
	ClosePrice        float64 `json:"close_price"`
	NetForeignFlow5d  float64 `json:"net_foreign_flow_5d"`
	NetForeignFlow20d float64 `json:"net_foreign_flow_20d"`
	RSI14             float64 `json:"rsi_14"`
}

// BrokerConcentrationRecord represents broker concentration ratio.
type BrokerConcentrationRecord struct {
	StockCode    string  `json:"stock_code"`
	Top1BuyShare float64 `json:"top1_buy_share"`
	Top3BuyShare float64 `json:"top3_buy_share"`
	Top5BuyShare float64 `json:"top5_buy_share"`
	DominanceTier string `json:"dominance_tier"`
}

// ScanStealthAccumulation detects institutional absorption without price run-up.
func ScanStealthAccumulation(dataDir string, topN int) ([]StealthAccumulationRecord, error) {
	dash, err := LoadDashboardData(dataDir)
	if err != nil {
		return nil, err
	}

	compMap := make(map[string]models.Company)
	for _, c := range dash.Companies {
		compMap[c.Code] = c
	}

	stockDir := filepath.Join(dataDir, "timeseries", "stock_summary")
	entries, err := os.ReadDir(stockDir)
	if err != nil {
		return nil, err
	}

	var candidates []StealthAccumulationRecord

	// Collect tickers from partitions
	tickerSet := make(map[string]bool)
	for _, c := range dash.Companies {
		if c.CompounderScore >= 45.0 {
			tickerSet[c.Code] = true
		}
	}
	_ = entries

	for ticker := range tickerSet {
		records, latest, err := GetStockData(dataDir, ticker, 25)
		if err != nil || len(records) < 3 || latest == nil {
			continue
		}

		lastIdx := len(records) - 1
		startIdx := 0
		if len(records) > 20 {
			startIdx = len(records) - 20
		}

		startPrice := records[startIdx].Close
		currentPrice := latest.Close
		if startPrice <= 0 || currentPrice <= 0 {
			continue
		}

		priceChangePct := ((currentPrice - startPrice) / startPrice) * 100.0

		var nff20d, turnover20d float64
		for i := startIdx; i <= lastIdx; i++ {
			nff20d += records[i].NetForeignFlow
			turnover20d += records[i].Value
		}

		// Stealth criterion: positive foreign accumulation while price change is consolidating (-8% to +8%)
		if nff20d > 100_000 && priceChangePct >= -8.0 && priceChangePct <= 8.0 {
			flowIntensity := 0.0
			if turnover20d > 0 {
				flowIntensity = (nff20d * currentPrice / turnover20d) * 100.0
			}

			comp := compMap[ticker]
			candidates = append(candidates, StealthAccumulationRecord{
				StockCode:         ticker,
				CompanyName:       comp.Name,
				ClosePrice:        currentPrice,
				PriceChange20dPct: priceChangePct,
				NetForeignFlow20d: nff20d,
				Turnover20d:       turnover20d,
				FlowIntensityPct:  flowIntensity,
				DCAVerdict:        comp.DCAVerdict,
				CompounderScore:   comp.CompounderScore,
			})
		}
	}

	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].NetForeignFlow20d > candidates[j].NetForeignFlow20d
	})

	if topN > 0 && len(candidates) > topN {
		candidates = candidates[:topN]
	}

	return candidates, nil
}

// GetForeignFlowScreen ranks top foreign money accumulation.
func GetForeignFlowScreen(dataDir string, topN int) ([]ForeignFlowRank, error) {
	dash, err := LoadDashboardData(dataDir)
	if err != nil {
		return nil, err
	}

	var results []ForeignFlowRank
	for _, c := range dash.Companies {
		if c.EstimatedMCap < 500.0 {
			continue
		}
		records, latest, err := GetStockData(dataDir, c.Code, 22)
		if err != nil || len(records) < 3 || latest == nil {
			continue
		}

		lastIdx := len(records) - 1
		startIdx := 0
		if len(records) > 20 {
			startIdx = len(records) - 20
		}
		fiveStart := 0
		if len(records) > 5 {
			fiveStart = len(records) - 5
		}

		var nff20d, nff5d float64
		for i := startIdx; i <= lastIdx; i++ {
			nff20d += records[i].NetForeignFlow
		}
		for i := fiveStart; i <= lastIdx; i++ {
			nff5d += records[i].NetForeignFlow
		}

		rsi := 50.0
		if records[lastIdx].RSI14 != nil {
			rsi = *records[lastIdx].RSI14
		}

		results = append(results, ForeignFlowRank{
			StockCode:         c.Code,
			CompanyName:       c.Name,
			ClosePrice:        latest.Close,
			NetForeignFlow5d:  nff5d,
			NetForeignFlow20d: nff20d,
			RSI14:             rsi,
		})
	}

	sort.Slice(results, func(i, j int) bool {
		return results[i].NetForeignFlow20d > results[j].NetForeignFlow20d
	})

	if topN > 0 && len(results) > topN {
		results = results[:topN]
	}

	return results, nil
}

// FormatIDRBillion formats large numbers into billions of IDR.
func FormatIDRBillion(val float64) string {
	if math.Abs(val) >= 1e12 {
		return fmt.Sprintf("Rp %.2f T", val/1e12)
	}
	return fmt.Sprintf("Rp %.2f B", val/1e9)
}

// BandarAnomalyAlert represents an intraday or session volume/flow anomaly crossing 3σ.
type BandarAnomalyAlert struct {
	StockCode          string  `json:"stock_code"`
	CompanyName        string  `json:"company_name"`
	ClosePrice         float64 `json:"close_price"`
	PriceChangePct     float64 `json:"price_change_pct"`
	Volume             float64 `json:"volume"`
	TurnoverRp         float64 `json:"turnover_rp"`
	NetForeignFlowRp   float64 `json:"net_foreign_flow_rp"`
	ForeignBuyRatioPct float64 `json:"foreign_buy_ratio_pct"`
	ZScoreVolume       float64 `json:"z_score_volume"`
	ZScoreNFF          float64 `json:"z_score_nff"`
	ZComposite         float64 `json:"z_composite"`
	AnomalyType        string  `json:"anomaly_type"`
	WyckoffPhase       string  `json:"wyckoff_phase"`
	Playbook           string  `json:"playbook"`
}

// DetectBandarAnomalies scans local stock time-series data for statistical volume/flow outliers.
func DetectBandarAnomalies(dataDir string, threshold float64, topN int) ([]BandarAnomalyAlert, error) {
	dash, err := LoadDashboardData(dataDir)
	if err != nil {
		return nil, err
	}

	var alerts []BandarAnomalyAlert

	for _, c := range dash.Companies {
		records, latest, err := GetStockData(dataDir, c.Code, 25)
		if err != nil || len(records) < 15 || latest == nil {
			continue
		}

		lastIdx := len(records) - 1
		prev := records[lastIdx-1]
		if prev.Close <= 0 || latest.Close <= 0 {
			continue
		}

		priceChgPct := (latest.Close - prev.Close) / prev.Close * 100.0

		// Baseline 20 sessions (or available)
		lookback := 20
		if len(records)-1 < lookback {
			lookback = len(records) - 1
		}
		startIdx := lastIdx - lookback

		var sumVol, sumVolSq, sumVal, sumNff, sumNffSq float64
		count := float64(lookback)

		for i := startIdx; i < lastIdx; i++ {
			r := records[i]
			sumVol += r.Volume
			sumVolSq += r.Volume * r.Volume
			sumVal += r.Value
			sumNff += r.NetForeignFlow
			sumNffSq += r.NetForeignFlow * r.NetForeignFlow
		}

		meanVol := sumVol / count
		varianceVol := (sumVolSq / count) - (meanVol * meanVol)
		stdVol := math.Sqrt(math.Max(0, varianceVol))
		if stdVol <= 0 {
			stdVol = meanVol*0.3 + 1000.0
		}
		stdVol = math.Max(stdVol, math.Max(meanVol*0.1, 10000.0))

		meanNff := sumNff / count
		varianceNff := (sumNffSq / count) - (meanNff * meanNff)
		stdNff := math.Sqrt(math.Max(0, varianceNff))
		if stdNff <= 0 {
			stdNff = math.Abs(meanNff)*0.4 + 1e8
		}
		stdNff = math.Max(stdNff, 1e8)

		zVol := (latest.Volume - meanVol) / stdVol
		zNff := (latest.NetForeignFlow - meanNff) / stdNff

		// Clamp
		zVol = math.Max(-25.0, math.Min(25.0, zVol))
		zNff = math.Max(-25.0, math.Min(25.0, zNff))
		zComp := math.Max(zVol, zNff)

		if zComp < threshold && zVol < threshold && zNff < threshold {
			continue
		}

		fbRatio := 0.0
		if latest.Volume > 0 && latest.ForeignBuy > 0 {
			fbRatio = (latest.ForeignBuy / latest.Volume) * 100.0
		}

		anomalyType := "NEUTRAL"
		wyckoff := "Phase B — Building Cause"
		playbook := "Monitor orderbook depth."

		if (zVol >= threshold || zNff >= 2.0) && fbRatio >= 55.0 && math.Abs(priceChgPct) <= 1.5 {
			anomalyType = "INSTITUTIONAL_ABSORPTION"
			wyckoff = "Phase C — Silent Absorption / Spring Accumulation"
			playbook = fmt.Sprintf("Smart money absorbed %.1f%% of total volume with flat price. Supply being dried up.", fbRatio)
		} else if (zVol >= threshold || zNff >= 2.0) && fbRatio >= 60.0 && priceChgPct > 1.5 {
			anomalyType = "INSTITUTIONAL_MARKUP"
			wyckoff = "Phase D — Markup Breakout / Sign of Strength"
			playbook = fmt.Sprintf("Aggressive institutional buy aggression lifting ask prices (+%.1f%%). Momentum continuation.", priceChgPct)
		} else if zVol >= threshold && (fbRatio < 25.0 || zNff <= -1.5) && priceChgPct > 0.5 {
			anomalyType = "RETAIL_TRAP_DISTRIBUTION"
			wyckoff = "Phase B/C — Upthrust After Distribution (UTAD) / Retail Trap"
			playbook = "Price pushed up while smart hands net distribute. Retail trap risk."
		} else if zNff <= -threshold || (zVol >= threshold && zNff <= -2.0) {
			anomalyType = "INSTITUTIONAL_DUMP"
			wyckoff = "Phase E — Markdown / Liquidation"
			playbook = "Heavy institutional dumping. Do not catch falling knife."
		} else {
			continue
		}

		alerts = append(alerts, BandarAnomalyAlert{
			StockCode:          c.Code,
			CompanyName:        c.Name,
			ClosePrice:         latest.Close,
			PriceChangePct:     priceChgPct,
			Volume:             latest.Volume,
			TurnoverRp:         latest.Value,
			NetForeignFlowRp:   latest.NetForeignFlow,
			ForeignBuyRatioPct: fbRatio,
			ZScoreVolume:       zVol,
			ZScoreNFF:          zNff,
			ZComposite:         zComp,
			AnomalyType:        anomalyType,
			WyckoffPhase:       wyckoff,
			Playbook:           playbook,
		})
	}

	sort.Slice(alerts, func(i, j int) bool {
		return alerts[i].ZComposite > alerts[j].ZComposite
	})

	if topN > 0 && len(alerts) > topN {
		alerts = alerts[:topN]
	}

	return alerts, nil
}
