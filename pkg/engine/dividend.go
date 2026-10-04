package engine

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"

	"github.com/nichsedge/idx-bei/pkg/models"
)

var (
	companyDetailsLock  sync.RWMutex
	companyDetailsCache RawCompanyDetails
)

// RawCompanyDetails maps companyDetailsByKodeEmiten.json structure.
type RawCompanyDetails map[string]struct {
	Dividen []RawDividend `json:"Dividen"`
	Profiles []struct {
		NamaEmiten string `json:"NamaEmiten"`
	} `json:"Profiles"`
}

// LoadCompanyDetails loads and caches companyDetailsByKodeEmiten.json in memory.
func LoadCompanyDetails(dataDir string) (RawCompanyDetails, error) {
	companyDetailsLock.RLock()
	if companyDetailsCache != nil {
		defer companyDetailsLock.RUnlock()
		return companyDetailsCache, nil
	}
	companyDetailsLock.RUnlock()

	detailsFile := filepath.Join(dataDir, "companyDetailsByKodeEmiten.json")
	detailsData, err := os.ReadFile(detailsFile)
	if err != nil {
		return nil, fmt.Errorf("failed reading company details: %w", err)
	}

	var allDetails RawCompanyDetails
	if err := json.Unmarshal(detailsData, &allDetails); err != nil {
		return nil, fmt.Errorf("failed parsing company details: %w", err)
	}

	companyDetailsLock.Lock()
	companyDetailsCache = allDetails
	companyDetailsLock.Unlock()

	return allDetails, nil
}

type RawDividend struct {
	Nama                         string  `json:"Nama"`
	Jenis                        string  `json:"Jenis"`
	TahunBuku                    string  `json:"TahunBuku"`
	CashDividenPerSahamMU        string  `json:"CashDividenPerSahamMU"`
	CashDividenPerSaham          float64 `json:"CashDividenPerSaham"`
	CashDividenTotalMU           string  `json:"CashDividenTotalMU"`
	CashDividenTotal             float64 `json:"CashDividenTotal"`
	TanggalCum                   string  `json:"TanggalCum"`
	TanggalExRegulerDanNegosiasi string  `json:"TanggalExRegulerDanNegosiasi"`
	TanggalDPS                   string  `json:"TanggalDPS"`
	TanggalPembayaran            string  `json:"TanggalPembayaran"`
}

// DividendDecision holds full quantitative risk assessment for a stock dividend.
type DividendDecision struct {
	Ticker             string   `json:"ticker"`
	CompanyName        string   `json:"company_name"`
	HasDividend        bool     `json:"has_dividend"`
	CurrentPrice       float64  `json:"current_price"`
	DPS                float64  `json:"dps_idr"`
	DivYieldPct        float64  `json:"div_yield_pct"`
	DPRPct             float64  `json:"dpr_pct"`
	RSI14              float64  `json:"rsi_14"`
	Runup20dPct        float64  `json:"runup_20d_pct"`
	NetForeignFlow20d  float64  `json:"net_foreign_flow_20d"`
	TrapScore          float64  `json:"trap_score"`
	TrapRiskTier       string   `json:"trap_risk_tier"`
	Recommendation     string   `json:"recommendation"`
	TacticalPlaybook   string   `json:"tactical_playbook"`
	RiskFactors        []string `json:"risk_factors"`
	CumDate            string   `json:"cum_date"`
	ExDate             string   `json:"ex_date"`
	PaymentDate        string   `json:"payment_date"`
}

func getUSDIDRRate(dataDir string) float64 {
	rateFile := filepath.Join(dataDir, "usd_idr_rate.json")
	if data, err := os.ReadFile(rateFile); err == nil {
		var r struct {
			Rate float64 `json:"rate"`
		}
		if err := json.Unmarshal(data, &r); err == nil && r.Rate > 0 {
			return r.Rate
		}
	}
	return 16250.0
}

// AnalyzeDividend performs deep quantitative dividend risk analysis for a ticker.
func AnalyzeDividend(dataDir, ticker string) (*DividendDecision, error) {
	ticker = strings.ToUpper(strings.TrimSpace(ticker))
	allDetails, err := LoadCompanyDetails(dataDir)
	if err != nil {
		return nil, err
	}

	comp, ok := allDetails[ticker]
	if !ok || len(comp.Dividen) == 0 {
		return &DividendDecision{
			Ticker:      ticker,
			HasDividend: false,
		}, nil
	}

	latestDiv := comp.Dividen[0]
	compName := latestDiv.Nama
	if compName == "" && len(comp.Profiles) > 0 {
		compName = comp.Profiles[0].NamaEmiten
	}

	// Fetch stock trading records
	records, latestRec, err := GetStockData(dataDir, ticker, 30)
	currentPrice := 0.0
	if latestRec != nil {
		currentPrice = latestRec.Close
	}

	usdRate := getUSDIDRRate(dataDir)

	// Calculate DPS in IDR
	dpsRaw := latestDiv.CashDividenPerSaham
	dpsMU := strings.ToUpper(strings.TrimSpace(latestDiv.CashDividenPerSahamMU))
	dpsIDR := dpsRaw
	if dpsMU == "USD" {
		dpsIDR = dpsRaw * usdRate
		if currentPrice > 0 && dpsIDR > currentPrice*0.6 {
			dpsIDR /= 100.0 // cents adjustment
		}
	} else if currentPrice > 0 && dpsRaw > currentPrice*0.7 {
		dpsIDR = dpsRaw / 1000.0
	}

	yieldPct := 0.0
	if currentPrice > 0 {
		yieldPct = (dpsIDR / currentPrice) * 100.0
	}

	// Fetch company fundamentals
	dash, _ := LoadDashboardData(dataDir)
	var fundCompany *models.Company
	if dash != nil {
		for i := range dash.Companies {
			if dash.Companies[i].Code == ticker {
				fundCompany = &dash.Companies[i]
				break
			}
		}
	}

	dprPct := 0.0
	if fundCompany != nil && fundCompany.EPS > 0 {
		dprPct = (dpsIDR / fundCompany.EPS) * 100.0
	}

	// Momentum & RSI
	rsi14 := 50.0
	runup20d := 0.0
	nff20d := 0.0
	nff5d := 0.0

	if len(records) > 0 {
		lastIdx := len(records) - 1
		if records[lastIdx].RSI14 != nil {
			rsi14 = *records[lastIdx].RSI14
		}

		startIdx := 0
		if len(records) > 20 {
			startIdx = len(records) - 20
		}
		startPrice := records[startIdx].Close
		if startPrice > 0 {
			runup20d = ((currentPrice - startPrice) / startPrice) * 100.0
		}

		for i := startIdx; i <= lastIdx; i++ {
			nff20d += records[i].NetForeignFlow
		}
		fiveStart := 0
		if len(records) > 5 {
			fiveStart = len(records) - 5
		}
		for i := fiveStart; i <= lastIdx; i++ {
			nff5d += records[i].NetForeignFlow
		}
	}

	// Quantitative Dividend Trap Risk Scoring (0-100)
	trapScore := 0.0
	var riskFactors []string

	// Dim 1: Yield severity
	if yieldPct >= 12.0 {
		trapScore += 25.0
		riskFactors = append(riskFactors, fmt.Sprintf("Ultra-high yield (%.1f%%): severe multi-day Ex-Date ARB markdown risk", yieldPct))
	} else if yieldPct >= 8.0 {
		trapScore += 18.0
		riskFactors = append(riskFactors, fmt.Sprintf("High yield (%.1f%%): expected steep Ex-Date markdown", yieldPct))
	} else if yieldPct >= 5.0 {
		trapScore += 10.0
	} else {
		trapScore += 2.0
	}

	// Dim 2: DPR
	if dprPct > 100.0 {
		trapScore += 25.0
		riskFactors = append(riskFactors, fmt.Sprintf("Unsustainable payout (DPR %.1f%% > 100%%): capital eroding", dprPct))
	} else if dprPct > 80.0 {
		trapScore += 18.0
		riskFactors = append(riskFactors, fmt.Sprintf("Aggressive payout (DPR %.1f%%): vulnerable to earnings slump", dprPct))
	} else if dprPct > 60.0 {
		trapScore += 8.0
	}

	// Dim 3: Smart money flow
	if nff5d < 0 && runup20d > 5.0 {
		trapScore += 20.0
		riskFactors = append(riskFactors, "Smart Money Divergence: Foreigners net selling into pre-cum price run-up")
	} else if nff20d < 0 {
		trapScore += 10.0
		riskFactors = append(riskFactors, fmt.Sprintf("Foreign outflow: Net selling of Rp %.1fB over 20d", -nff20d/1e9))
	} else if nff20d > 0 {
		trapScore -= 5.0
	}

	// Dim 4: Technical euphoria
	if rsi14 >= 75.0 || runup20d >= 20.0 {
		trapScore += 15.0
		riskFactors = append(riskFactors, fmt.Sprintf("Overbought euphoria: RSI-14 is %.1f, 20d run-up +%.1f%%", rsi14, runup20d))
	} else if rsi14 >= 68.0 || runup20d >= 10.0 {
		trapScore += 8.0
		riskFactors = append(riskFactors, fmt.Sprintf("Elevated momentum: RSI-14 is %.1f", rsi14))
	}

	// Dim 5: Leverage
	if fundCompany != nil && fundCompany.DERatio > 2.5 && fundCompany.ROE < 10.0 {
		trapScore += 10.0
		riskFactors = append(riskFactors, fmt.Sprintf("High leverage (DER %.2fx) with weak ROE (%.1f%%)", fundCompany.DERatio, fundCompany.ROE))
	}

	if trapScore < 0 {
		trapScore = 0
	}
	if trapScore > 100 {
		trapScore = 100
	}

	tier := "LOW"
	recommendation := "BUY_ACCUMULATE"
	playbook := "Hold through Cum Date to capture full dividend yield. Low risk of Ex-Date trap."

	if trapScore > 60.0 {
		tier = "SEVERE"
		recommendation = "SELL_BEFORE_CUM"
		playbook = "Exit position 1-2 sessions prior to Cum Date close to lock in capital gains and evade steep Ex-Date gap down."
	} else if trapScore > 40.0 {
		tier = "MODERATE"
		recommendation = "HOLD_HARVEST"
		playbook = "Hold existing position but avoid aggressive pre-cum chasing. Set trailing stop-loss."
	}

	cumDate := latestDiv.TanggalCum
	if len(cumDate) > 10 {
		cumDate = cumDate[:10]
	}
	exDate := latestDiv.TanggalExRegulerDanNegosiasi
	if len(exDate) > 10 {
		exDate = exDate[:10]
	}
	payDate := latestDiv.TanggalPembayaran
	if len(payDate) > 10 {
		payDate = payDate[:10]
	}

	return &DividendDecision{
		Ticker:            ticker,
		CompanyName:       compName,
		HasDividend:       true,
		CurrentPrice:      currentPrice,
		DPS:               dpsIDR,
		DivYieldPct:       yieldPct,
		DPRPct:            dprPct,
		RSI14:             rsi14,
		Runup20dPct:       runup20d,
		NetForeignFlow20d: nff20d,
		TrapScore:         trapScore,
		TrapRiskTier:      tier,
		Recommendation:    recommendation,
		TacticalPlaybook:  playbook,
		RiskFactors:       riskFactors,
		CumDate:           cumDate,
		ExDate:            exDate,
		PaymentDate:       payDate,
	}, nil
}

// ScreenDividends scans all tickers with dividends and returns ranked decisions.
func ScreenDividends(dataDir string, minYield float64, limit int) ([]DividendDecision, error) {
	allDetails, err := LoadCompanyDetails(dataDir)
	if err != nil {
		return nil, err
	}

	var tickers []string
	for t, comp := range allDetails {
		if len(comp.Dividen) > 0 {
			tickers = append(tickers, t)
		}
	}
	sort.Strings(tickers)

	var results []DividendDecision
	for _, t := range tickers {
		dec, err := AnalyzeDividend(dataDir, t)
		if err != nil || dec == nil || !dec.HasDividend {
			continue
		}
		if dec.DivYieldPct >= minYield {
			results = append(results, *dec)
		}
	}

	sort.Slice(results, func(i, j int) bool {
		return results[i].DivYieldPct > results[j].DivYieldPct
	})

	if limit > 0 && len(results) > limit {
		results = results[:limit]
	}

	return results, nil
}
