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
