package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/nichsedge/idx-bei/pkg/api"
	"github.com/nichsedge/idx-bei/pkg/engine"
	"github.com/nichsedge/idx-bei/pkg/ingest"
	"github.com/nichsedge/idx-bei/pkg/mcp"
)

func usage() {
	fmt.Println("IDX-BEI Quantitative & Market Intelligence Toolkit (Go)")
	fmt.Println()
	fmt.Println("Usage:")
	fmt.Println("  idx serve [--port 8000]       Start high-performance REST & WebSocket server")
	fmt.Println("  idx dashboard [--port 8000]   Start visual web dashboard & API server")
	fmt.Println("  idx sync [--date YYYYMMDD]    Ingest market close data via uTLS")
	fmt.Println("  idx status                    Display dataset inventory and partition counts")
	fmt.Println("  idx compounder [TICKER]       Screen institutional DCA compounders")
	fmt.Println("  idx stock <TICKER>            Inspect technical indicators & OHLCV for ticker")
	fmt.Println("  idx dividend <TICKER>         Analyze dividend decision & Ex-Date trap risk")
	fmt.Println("  idx dividend --screen         Rank all dividend opportunities by net yield")
	fmt.Println("  idx signals                   Display daily foreign flow & stealth accumulation")
	fmt.Println("  idx bandarmology [--stealth]  Inspect broker flows & stealth institutional buying")
	fmt.Println("  idx backtest [--strategy ...] Run vectorized strategy performance simulation")
	fmt.Println("  idx mcp                       Start Model Context Protocol (MCP) stdio server")
	fmt.Println()
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(0)
	}

	cmd := os.Args[1]
	args := os.Args[2:]

	dataDir := resolveDataDir()

	switch cmd {
	case "serve", "dashboard":
		fs := flag.NewFlagSet(cmd, flag.ExitOnError)
		host := fs.String("host", "0.0.0.0", "Host to bind")
		port := fs.Int("port", 8000, "Port to listen on")
		fs.Parse(args)

		cfg := api.ServerConfig{
			Host:    *host,
			Port:    *port,
			DataDir: dataDir,
		}

		addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
		fmt.Printf("=== Starting IDX-BEI Microservice Server on http://localhost:%d/ ===\n", cfg.Port)
		fmt.Printf("  • Web Dashboard:  http://localhost:%d/\n", cfg.Port)
		fmt.Printf("  • REST API:       http://localhost:%d/health\n", cfg.Port)
		fmt.Printf("  • WebSocket:      ws://localhost:%d/ws/stream\n", cfg.Port)
		fmt.Printf("  • Data Dir:       %s\n", cfg.DataDir)

		router := api.NewRouter(cfg)
		if err := http.ListenAndServe(addr, router); err != nil {
			log.Fatalf("Server failed: %v", err)
		}

	case "sync", "daily":
		fs := flag.NewFlagSet("sync", flag.ExitOnError)
		date := fs.String("date", "", "Date in YYYYMMDD format (default: today)")
		webhook := fs.String("webhook", "", "Optional webhook URL")
		fs.Parse(args)

		opts := ingest.SyncOptions{
			Date:       *date,
			DataDir:    dataDir,
			WebhookURL: *webhook,
		}
		summary, err := ingest.RunDailySync(opts)
		if err != nil {
			log.Fatalf("Sync error: %v", err)
		}
		fmt.Printf("✓ Ingestion complete for %s\n", summary.Date)

	case "status":
		tsDir := filepath.Join(dataDir, "timeseries")
		datasets := []string{"stock_summary", "broker_summary", "index_summary"}
		fmt.Println("=== IDX-BEI Dataset Inventory ===")
		for _, ds := range datasets {
			pDir := filepath.Join(tsDir, ds)
			entries, _ := os.ReadDir(pDir)
			dates := 0
			for _, e := range entries {
				if strings.HasPrefix(e.Name(), "date=") {
					dates++
				}
			}
			fmt.Printf("  • %-16s: %d partitions\n", ds, dates)
		}
		if rate, err := os.ReadFile(filepath.Join(dataDir, "usd_idr_rate.json")); err == nil {
			var r struct {
				Rate float64 `json:"rate"`
			}
			json.Unmarshal(rate, &r)
			fmt.Printf("  • USD/IDR Rate    : Rp %.2f\n", r.Rate)
		}

	case "compounder":
		fs := flag.NewFlagSet("compounder", flag.ExitOnError)
		topN := fs.Int("top", 15, "Top N compounders to show")
		minScore := fs.Float64("min-score", 60.0, "Minimum compounder score")
		showTraps := fs.Bool("show-traps", false, "Show accounting value traps")
		fs.Parse(args)

		// Check if ticker is provided as positional argument
		var targetTicker string
		for _, a := range fs.Args() {
			if !strings.HasPrefix(a, "-") {
				targetTicker = strings.ToUpper(a)
				break
			}
		}

		if targetTicker != "" {
			dash, err := engine.LoadDashboardData(dataDir)
			if err != nil {
				log.Fatalf("Error: %v", err)
			}
			for _, c := range dash.Companies {
				if c.Code == targetTicker {
					fmt.Printf("\n=== Forensic & Compounder Profile: %s (%s) ===\n", c.Code, c.Name)
					fmt.Printf("  Sector:          %s (%s)\n", c.Sector, c.SubSector)
					fmt.Printf("  DCA Verdict:     %s\n", c.DCAVerdict)
					fmt.Printf("  Compounder Score: %.2f / 100\n", c.CompounderScore)
					fmt.Printf("  Valuation:       %s (PBV: %.2fx, PER: %.2fx)\n", c.ValuationStatus, c.PriceBV, c.PER)
					fmt.Printf("  Fundamentals:    ROE: %.2f%%, NPM: %.2f%%, DER: %.2fx\n", c.ROE, c.NPM, c.DERatio)
					if c.IsValueTrap {
						fmt.Println("  ⚠️ WARNING: Identified Accounting Value Trap (one-off distortion / high leverage)")
					}
					return
				}
			}
			fmt.Printf("Ticker '%s' not found.\n", targetTicker)
			return
		}

		res, err := engine.GetCompounderScreen(dataDir, *minScore, !*showTraps, "", *topN)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		fmt.Printf("\n=== Top Long-Term DCA Compounders (Min Score: %.0f) ===\n", *minScore)
		fmt.Printf("%-6s %-32s %-16s %-8s %-6s %-6s %-6s\n", "Code", "Company Name", "Sector", "Verdict", "Score", "PBV", "ROE")
		fmt.Println(strings.Repeat("─", 86))
		for _, c := range res {
			name := c.Name
			if len(name) > 30 {
				name = name[:30] + ".."
			}
			sec := c.Sector
			if len(sec) > 15 {
				sec = sec[:15]
			}
			fmt.Printf("%-6s %-32s %-16s %-8s %-6.1f %-6.2f %-6.1f\n",
				c.Code, name, sec, c.DCAVerdict, c.CompounderScore, c.PriceBV, c.ROE)
		}

	case "stock":
		if len(args) == 0 {
			fmt.Println("Usage: idx stock <TICKER> [LIMIT]")
			return
		}
		ticker := strings.ToUpper(args[0])
		limit := 10
		if len(args) > 1 {
			if l, err := strconv.Atoi(args[1]); err == nil {
				limit = l
			}
		}

		records, latest, err := engine.GetStockData(dataDir, ticker, limit)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		fmt.Printf("\n=== %s Trading History & Technical Indicators ===\n", ticker)
		fmt.Printf("%-12s %-8s %-8s %-8s %-8s %-10s %-8s %-8s\n",
			"Date", "Open", "High", "Low", "Close", "Volume", "RSI(14)", "EMA(20)")
		fmt.Println(strings.Repeat("─", 78))
		for _, r := range records {
			rsiStr := "-"
			if r.RSI14 != nil {
				rsiStr = fmt.Sprintf("%.1f", *r.RSI14)
			}
			emaStr := "-"
			if r.EMA20 != nil {
				emaStr = fmt.Sprintf("%.0f", *r.EMA20)
			}
			d := r.Date
			if len(d) > 10 {
				d = d[:10]
			}
			fmt.Printf("%-12s %-8.0f %-8.0f %-8.0f %-8.0f %-10.0f %-8s %-8s\n",
				d, r.Open, r.High, r.Low, r.Close, r.Volume, rsiStr, emaStr)
		}
		if latest != nil {
			fmt.Printf("\nLatest Close: Rp %.0f | Net Foreign Flow: Rp %.0f\n", latest.Close, latest.NetForeignFlow)
		}

	case "dividend":
		fs := flag.NewFlagSet("dividend", flag.ExitOnError)
		screen := fs.Bool("screen", false, "Screen and rank all dividend opportunities")
		minYield := fs.Float64("min-yield", 4.0, "Minimum dividend yield percentage")
		limit := fs.Int("limit", 15, "Limit number of results")
		fs.Parse(args)

		if *screen {
			res, err := engine.ScreenDividends(dataDir, *minYield, *limit)
			if err != nil {
				log.Fatalf("Dividend screen error: %v", err)
			}
			fmt.Printf("\n=== Top IDX Dividend Opportunities (Min Yield: %.1f%%) ===\n", *minYield)
			fmt.Printf("%-6s %-28s %-8s %-8s %-8s %-8s %-16s %-10s\n",
				"Code", "Company Name", "Yield", "DPS", "Price", "TrapRisk", "Recommendation", "Cum Date")
			fmt.Println(strings.Repeat("─", 100))
			for _, d := range res {
				name := d.CompanyName
				if len(name) > 26 {
					name = name[:26] + ".."
				}
				fmt.Printf("%-6s %-28s %-7.1f%% %-8.0f %-8.0f %-8.0f %-16s %-10s\n",
					d.Ticker, name, d.DivYieldPct, d.DPS, d.CurrentPrice, d.TrapScore, d.Recommendation, d.CumDate)
			}
			return
		}

		var targetTicker string
		for _, a := range fs.Args() {
			if !strings.HasPrefix(a, "-") {
				targetTicker = strings.ToUpper(a)
				break
			}
		}
		if targetTicker == "" {
			fmt.Println("Usage: idx dividend <TICKER> or idx dividend --screen [--min-yield 4.0]")
			return
		}

		dec, err := engine.AnalyzeDividend(dataDir, targetTicker)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		if !dec.HasDividend {
			fmt.Printf("No active dividend distribution record found for '%s'.\n", targetTicker)
			return
		}

		fmt.Printf("\n=== Dividend Decision & Trap Profile: %s (%s) ===\n", dec.Ticker, dec.CompanyName)
		fmt.Printf("  • Current Price:        Rp %.0f\n", dec.CurrentPrice)
		fmt.Printf("  • Cash DPS:             Rp %.2f\n", dec.DPS)
		fmt.Printf("  • Gross Dividend Yield: %.2f%%\n", dec.DivYieldPct)
		fmt.Printf("  • Payout Ratio (DPR):   %.1f%%\n", dec.DPRPct)
		fmt.Printf("  • Cum Date:             %s | Ex-Date: %s | Pay: %s\n", dec.CumDate, dec.ExDate, dec.PaymentDate)
		fmt.Printf("  • Trap Risk Score:      %.1f / 100 (%s RISK)\n", dec.TrapScore, dec.TrapRiskTier)
		fmt.Printf("  • Technical Regime:     RSI-14: %.1f | 20d Run-up: %+.1f%%\n", dec.RSI14, dec.Runup20dPct)
		fmt.Printf("  • Net Foreign Flow 20d: %s\n", engine.FormatIDRBillion(dec.NetForeignFlow20d))
		fmt.Printf("  • RECOMMENDATION:       %s\n", dec.Recommendation)
		fmt.Printf("  • Tactical Playbook:    %s\n", dec.TacticalPlaybook)
		if len(dec.RiskFactors) > 0 {
			fmt.Println("\n  Identified Risk Factors:")
			for _, rf := range dec.RiskFactors {
				fmt.Printf("    ⚠️ %s\n", rf)
			}
		}

	case "signals":
		fmt.Println("\n=== IDX-BEI Market Intelligence & Foreign Flow Signals ===")
		flows, err := engine.GetForeignFlowScreen(dataDir, 10)
		if err == nil {
			fmt.Printf("\n--- Top Foreign Inflow Accumulation (20-Day Flow) ---\n")
			fmt.Printf("%-6s %-28s %-10s %-14s %-14s %-8s\n",
				"Code", "Company Name", "Price", "NFF 5-Day", "NFF 20-Day", "RSI(14)")
			fmt.Println(strings.Repeat("─", 84))
			for _, f := range flows {
				name := f.CompanyName
				if len(name) > 26 {
					name = name[:26] + ".."
				}
				fmt.Printf("%-6s %-28s %-10.0f %-14s %-14s %-8.1f\n",
					f.StockCode, name, f.ClosePrice, engine.FormatIDRBillion(f.NetForeignFlow5d), engine.FormatIDRBillion(f.NetForeignFlow20d), f.RSI14)
			}
		}

		stealths, err := engine.ScanStealthAccumulation(dataDir, 10)
		if err == nil && len(stealths) > 0 {
			fmt.Printf("\n--- Stealth Institutional Absorption (Price Flat, Strong Foreign Buying) ---\n")
			fmt.Printf("%-6s %-28s %-10s %-10s %-14s %-10s %-10s\n",
				"Code", "Company Name", "Price", "20d Ret", "NFF 20-Day", "Score", "Verdict")
			fmt.Println(strings.Repeat("─", 94))
			for _, s := range stealths {
				name := s.CompanyName
				if len(name) > 26 {
					name = name[:26] + ".."
				}
				fmt.Printf("%-6s %-28s %-10.0f %+9.1f%% %-14s %-10.1f %-10s\n",
					s.StockCode, name, s.ClosePrice, s.PriceChange20dPct, engine.FormatIDRBillion(s.NetForeignFlow20d), s.CompounderScore, s.DCAVerdict)
			}
		}

	case "bandarmology":
		fs := flag.NewFlagSet("bandarmology", flag.ExitOnError)
		stealth := fs.Bool("stealth", false, "Scan for stealth institutional accumulation")
		topN := fs.Int("top", 10, "Number of candidates")
		fs.Parse(args)

		if *stealth || true {
			stealths, err := engine.ScanStealthAccumulation(dataDir, *topN)
			if err != nil {
				log.Fatalf("Error: %v", err)
			}
			fmt.Printf("\n=== Stealth Institutional Accumulation Radar (Top %d) ===\n", *topN)
			fmt.Printf("%-6s %-28s %-10s %-10s %-14s %-10s %-10s\n",
				"Code", "Company Name", "Price", "20d Ret", "NFF 20-Day", "Score", "Verdict")
			fmt.Println(strings.Repeat("─", 94))
			for _, s := range stealths {
				name := s.CompanyName
				if len(name) > 26 {
					name = name[:26] + ".."
				}
				fmt.Printf("%-6s %-28s %-10.0f %+9.1f%% %-14s %-10.1f %-10s\n",
					s.StockCode, name, s.ClosePrice, s.PriceChange20dPct, engine.FormatIDRBillion(s.NetForeignFlow20d), s.CompounderScore, s.DCAVerdict)
			}
		}

	case "backtest":
		fs := flag.NewFlagSet("backtest", flag.ExitOnError)
		strategy := fs.String("strategy", "foreign_flow", "Strategy: foreign_flow, composite_alpha")
		holding := fs.Int("holding", 20, "Holding period in trading sessions")
		stopLoss := fs.Float64("stop-loss", 7.0, "Stop loss percentage")
		takeProfit := fs.Float64("take-profit", 15.0, "Take profit percentage")
		topN := fs.Int("top", 10, "Top N stocks")
		fs.Parse(args)

		summary, err := engine.RunStrategyBacktest(dataDir, *strategy, *holding, *topN, *stopLoss, *takeProfit)
		if err != nil {
			log.Fatalf("Backtest error: %v", err)
		}
		fmt.Printf("\n=== Quantitative Strategy Backtest: %s (%dd Holding) ===\n", summary.Strategy, summary.HoldingDays)
		fmt.Printf("  • Total Trades:       %d (Won: %d | Lost: %d)\n", summary.TotalTrades, summary.WinningTrades, summary.LosingTrades)
		fmt.Printf("  • Win Rate:           %.1f%%\n", summary.WinRatePct)
		fmt.Printf("  • Avg Trade Return:   %+.2f%%\n", summary.AvgReturnPct)
		fmt.Printf("  • Cumulative Return:  %+.2f%%\n", summary.CumulativeRet)
		fmt.Printf("  • Max Drawdown:       -%.2f%%\n", summary.MaxDrawdownPct)
		fmt.Printf("  • Annualized Sharpe:  %.2f\n", summary.SharpeRatio)
		if len(summary.TopTrades) > 0 {
			fmt.Println("\n  Top Sample Trades:")
			for _, t := range summary.TopTrades {
				fmt.Printf("    • %-5s %s -> %s: %+.1f%% (%s)\n",
					t.StockCode, t.EntryDate, t.ExitDate, t.ReturnPct, t.ExitReason)
			}
		}

	case "mcp":
		if err := mcp.ServeStdio(dataDir); err != nil {
			log.Fatalf("MCP server error: %v", err)
		}

	default:
		usage()
	}
}

func resolveDataDir() string {
	cwd, _ := os.Getwd()
	candidates := []string{
		filepath.Join(cwd, "data"),
		filepath.Join(cwd, "..", "data"),
		filepath.Join(os.Getenv("HOME"), "Projects", "idx-bei", "data"),
	}
	for _, c := range candidates {
		if info, err := os.Stat(c); err == nil && info.IsDir() {
			return c
		}
	}
	return "data"
}
