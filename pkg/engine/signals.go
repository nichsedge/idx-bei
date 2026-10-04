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
