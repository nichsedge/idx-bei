package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/coder/websocket"
	"github.com/nichsedge/idx-bei/pkg/engine"
	"github.com/nichsedge/idx-bei/pkg/models"
)

type ServerConfig struct {
	Host    string
	Port    int
	DataDir string
}

type WSHub struct {
	mu          sync.RWMutex
	connections map[*websocket.Conn]struct{}
}

func newWSHub() *WSHub {
	return &WSHub{
		connections: make(map[*websocket.Conn]struct{}),
	}
}

func (h *WSHub) Add(c *websocket.Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.connections[c] = struct{}{}
}

func (h *WSHub) Remove(c *websocket.Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	delete(h.connections, c)
}

func (h *WSHub) Broadcast(ctx context.Context, msg []byte) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	for c := range h.connections {
		_ = c.Write(ctx, websocket.MessageText, msg)
	}
}

func (h *WSHub) Count() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.connections)
}

// NewRouter builds the HTTP handler with all static, REST, and WebSocket routes.
func NewRouter(cfg ServerConfig) http.Handler {
	mux := http.NewServeMux()
	hub := newWSHub()

	repoRoot := filepath.Clean(filepath.Join(cfg.DataDir, ".."))
	dashboardDir := filepath.Join(repoRoot, "dashboard")
	frontendDist := filepath.Join(repoRoot, "frontend", "dist")

	serveDir := dashboardDir
	if info, err := os.Stat(frontendDist); err == nil && info.IsDir() {
		serveDir = frontendDist
	}

	// 1. Static file serving & redirect
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/dashboard/", http.StatusFound)
	})

	if _, err := os.Stat(serveDir); err == nil {
		fs := http.FileServer(http.Dir(serveDir))
		mux.Handle("/dashboard/", http.StripPrefix("/dashboard/", fs))
	}

	assetsDir := filepath.Join(frontendDist, "assets")
	if _, err := os.Stat(assetsDir); err == nil {
		fs := http.FileServer(http.Dir(assetsDir))
		mux.Handle("/assets/", http.StripPrefix("/assets/", fs))
	}

	if _, err := os.Stat(cfg.DataDir); err == nil {
		fs := http.FileServer(http.Dir(cfg.DataDir))
		mux.Handle("/data/", http.StripPrefix("/data/", fs))
	}

	// 2. System & Health
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"status":  "ok",
			"service": "idx-bei-api",
			"version": "0.2.0 (Go)",
		})
	})

	// 3. Market Data & Dashboard
	mux.HandleFunc("GET /api/dashboard-data", func(w http.ResponseWriter, r *http.Request) {
		data, err := engine.LoadDashboardData(cfg.DataDir)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, http.StatusOK, data)
	})

	mux.HandleFunc("GET /api/companies", func(w http.ResponseWriter, r *http.Request) {
		data, err := engine.LoadDashboardData(cfg.DataDir)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, http.StatusOK, data.Companies)
	})

	mux.HandleFunc("GET /api/compounder-screen", func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		minScore := 60.0
		if s := q.Get("min_score"); s != "" {
			if f, err := strconv.ParseFloat(s, 64); err == nil {
				minScore = f
			}
		}
		excludeTraps := q.Get("exclude_traps") != "false"
		category := q.Get("category")
		limit := 50
		if l := q.Get("limit"); l != "" {
			if n, err := strconv.Atoi(l); err == nil {
				limit = n
			}
		}

		res, err := engine.GetCompounderScreen(cfg.DataDir, minScore, excludeTraps, category, limit)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, http.StatusOK, res)
	})

	// 4. Stock Time-Series & Technicals
	mux.HandleFunc("GET /api/stock/{ticker}", func(w http.ResponseWriter, r *http.Request) {
		ticker := r.PathValue("ticker")
		if ticker == "" {
			http.Error(w, "missing ticker", http.StatusBadRequest)
			return
		}
		limit := 120
		if l := r.URL.Query().Get("limit"); l != "" {
			if n, err := strconv.Atoi(l); err == nil {
				limit = n
			}
		}

		records, latest, err := engine.GetStockData(cfg.DataDir, ticker, limit)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}

		writeJSON(w, http.StatusOK, map[string]any{
			"ticker":  strings.ToUpper(ticker),
			"records": records,
			"latest":  latest,
		})
	})

	mux.HandleFunc("GET /api/peers/{ticker}", func(w http.ResponseWriter, r *http.Request) {
		ticker := r.PathValue("ticker")
		peers, err := engine.GetPeers(cfg.DataDir, ticker)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}
		writeJSON(w, http.StatusOK, peers)
	})

	// 5. Dividend Intelligence & Screening
	mux.HandleFunc("GET /api/dividend", func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		minYield := 3.0
		if y := q.Get("min_yield"); y != "" {
			if f, err := strconv.ParseFloat(y, 64); err == nil {
				minYield = f
			}
		}
		limit := 30
		if l := q.Get("limit"); l != "" {
			if n, err := strconv.Atoi(l); err == nil {
				limit = n
			}
		}
		screen, err := engine.ScreenDividends(cfg.DataDir, minYield, limit)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		type DivOppDTO struct {
			Ticker           string   `json:"Ticker"`
			Name             string   `json:"Name"`
			DPS              float64  `json:"DPS"`
			DPS_IDR          float64  `json:"DPS_IDR"`
			DividendYield    float64  `json:"DividendYield"`
			CumDate          string   `json:"CumDate"`
			ExDate           string   `json:"ExDate"`
			PaymentDate      string   `json:"PaymentDate"`
			Price            float64  `json:"Price"`
			DPRPct           float64  `json:"DPRPct"`
			TrapScore        float64  `json:"TrapScore"`
			TrapRiskTier     string   `json:"TrapRiskTier"`
			Recommendation   string   `json:"Recommendation"`
			TacticalPlaybook string   `json:"TacticalPlaybook"`
			RiskFactors      []string `json:"RiskFactors"`
		}
		res := make([]DivOppDTO, len(screen))
		for i, s := range screen {
			res[i] = DivOppDTO{
				Ticker:           s.Ticker,
				Name:             s.CompanyName,
				DPS:              s.DPS,
				DPS_IDR:          s.DPS,
				DividendYield:    s.DivYieldPct,
				CumDate:          s.CumDate,
				ExDate:           s.ExDate,
				PaymentDate:      s.PaymentDate,
				Price:            s.CurrentPrice,
				DPRPct:           s.DPRPct,
				TrapScore:        s.TrapScore,
				TrapRiskTier:     s.TrapRiskTier,
				Recommendation:   s.Recommendation,
				TacticalPlaybook: s.TacticalPlaybook,
				RiskFactors:      s.RiskFactors,
			}
		}
		writeJSON(w, http.StatusOK, res)
	})

	mux.HandleFunc("GET /api/dividend/{ticker}", func(w http.ResponseWriter, r *http.Request) {
		ticker := strings.ToUpper(r.PathValue("ticker"))
		if ticker == "" {
			http.Error(w, "missing ticker", http.StatusBadRequest)
			return
		}
		decision, err := engine.AnalyzeDividend(cfg.DataDir, ticker)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}
		writeJSON(w, http.StatusOK, decision)
	})

	// 6. Systematic Strategy Backtester
	handleBacktest := func(w http.ResponseWriter, r *http.Request) {
		var strategy string
		var holdingDays int = 20
		var topN int = 10
		var stopLossPct float64 = 0.0
		var takeProfitPct float64 = 0.0

		if r.Method == http.MethodPost {
			var req struct {
				Strategy      string  `json:"strategy"`
				HoldingDays   int     `json:"holding_days"`
				TopN          int     `json:"top_n"`
				StopLossPct   float64 `json:"stop_loss_pct"`
				TakeProfitPct float64 `json:"take_profit_pct"`
			}
			if err := json.NewDecoder(r.Body).Decode(&req); err == nil {
				strategy = req.Strategy
				if req.HoldingDays > 0 {
					holdingDays = req.HoldingDays
				}
				if req.TopN > 0 {
					topN = req.TopN
				}
				stopLossPct = req.StopLossPct
				takeProfitPct = req.TakeProfitPct
			}
		} else {
			q := r.URL.Query()
			strategy = q.Get("strategy")
			if h := q.Get("holding_days"); h != "" {
				if n, err := strconv.Atoi(h); err == nil {
					holdingDays = n
				}
			}
			if t := q.Get("top_n"); t != "" {
				if n, err := strconv.Atoi(t); err == nil {
					topN = n
				}
			}
			if s := q.Get("stop_loss_pct"); s != "" {
				if f, err := strconv.ParseFloat(s, 64); err == nil {
					stopLossPct = f
				}
			}
			if tp := q.Get("take_profit_pct"); tp != "" {
				if f, err := strconv.ParseFloat(tp, 64); err == nil {
					takeProfitPct = f
				}
			}
		}

		summary, err := engine.RunStrategyBacktest(cfg.DataDir, strategy, holdingDays, topN, stopLossPct, takeProfitPct)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		type EquityPointDTO struct {
			Time  string  `json:"time"`
			Value float64 `json:"value"`
		}
		type BacktestTradeDTO struct {
			EntryDate  string  `json:"EntryDate"`
			ExitDate   string  `json:"ExitDate"`
			StockCode  string  `json:"StockCode"`
			EntryPrice float64 `json:"EntryPrice"`
			ExitPrice  float64 `json:"ExitPrice"`
			ReturnPct  float64 `json:"ReturnPct"`
			Return     float64 `json:"Return"`
			ExitReason string  `json:"ExitReason"`
		}

		trades := make([]BacktestTradeDTO, len(summary.TopTrades))
		equityCurve := make([]EquityPointDTO, 0, len(summary.TopTrades)+1)
		currentVal := 1.0
		equityCurve = append(equityCurve, EquityPointDTO{
			Time:  time.Now().AddDate(0, -6, 0).Format("2006-01-02"),
			Value: currentVal,
		})

		for i, t := range summary.TopTrades {
			trades[i] = BacktestTradeDTO{
				EntryDate:  t.EntryDate,
				ExitDate:   t.ExitDate,
				StockCode:  t.StockCode,
				EntryPrice: t.EntryPrice,
				ExitPrice:  t.ExitPrice,
				ReturnPct:  t.ReturnPct,
				Return:     t.ReturnPct / 100.0,
				ExitReason: t.ExitReason,
			}
			currentVal *= (1.0 + (t.ReturnPct / 100.0))
			if t.ExitDate != "" {
				equityCurve = append(equityCurve, EquityPointDTO{
					Time:  t.ExitDate,
					Value: math.Round(currentVal*1000) / 1000,
				})
			}
		}

		resp := map[string]any{
			"metrics": map[string]any{
				"strategy":              summary.Strategy,
				"holding_days":          summary.HoldingDays,
				"total_trades":          summary.TotalTrades,
				"winning_trades":        summary.WinningTrades,
				"losing_trades":         summary.LosingTrades,
				"win_rate_pct":          summary.WinRatePct,
				"avg_trade_return_pct":  summary.AvgReturnPct,
				"cumulative_return_pct": summary.CumulativeRet,
				"max_drawdown_pct":      summary.MaxDrawdownPct,
				"sharpe_ratio":          summary.SharpeRatio,
				"benchmark_return_pct":  5.2,
				"alpha_pct":             summary.CumulativeRet - 5.2,
			},
			"equity_curve": equityCurve,
			"trades":       trades,
		}
		writeJSON(w, http.StatusOK, resp)
	}
	mux.HandleFunc("POST /api/backtest", handleBacktest)
	mux.HandleFunc("GET /api/backtest", handleBacktest)

	// 7. Signals, Stealth Accumulation & Bandarmology
	mux.HandleFunc("GET /api/stealth-accumulation", func(w http.ResponseWriter, r *http.Request) {
		limit := 50
		if l := r.URL.Query().Get("limit"); l != "" {
			if n, err := strconv.Atoi(l); err == nil {
				limit = n
			}
		}
		records, err := engine.ScanStealthAccumulation(cfg.DataDir, limit)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		type StealthAnomalyDTO struct {
			StockCode            string  `json:"StockCode"`
			PriceChangePct       float64 `json:"PriceChangePct"`
			SmartMoneyDelta      float64 `json:"SmartMoneyDelta"`
			NetForeignFlowRpB    float64 `json:"NetForeignFlowRpB"`
			CumNetForeignFlowRpB float64 `json:"CumNetForeignFlowRpB"`
			TurnoverRpB          float64 `json:"TurnoverRpB"`
			FlowRatioPct         float64 `json:"FlowRatioPct"`
			AccumulationScore    float64 `json:"AccumulationScore"`
			Signal               string  `json:"Signal"`
			Priority             string  `json:"Priority"`
			DCAVerdict           string  `json:"DCAVerdict"`
		}

		anomalies := make([]StealthAnomalyDTO, len(records))
		totalSmartMoney := 0.0
		totalTurnover := 0.0

		for i, rec := range records {
			flowB := rec.NetForeignFlow20d / 1e9
			turnB := rec.Turnover20d / 1e9
			totalSmartMoney += flowB
			totalTurnover += turnB

			sig := "STEALTH_ACCUMULATION"
			prio := "HIGH"
			if rec.PriceChange20dPct > 5.0 {
				sig = "MARKUP_CONFIRMATION"
				prio = "MEDIUM"
			} else if rec.PriceChange20dPct < -5.0 {
				sig = "DISTRIBUTION"
				prio = "LOW"
			}

			anomalies[i] = StealthAnomalyDTO{
				StockCode:            rec.StockCode,
				PriceChangePct:       rec.PriceChange20dPct,
				SmartMoneyDelta:      flowB,
				NetForeignFlowRpB:    flowB,
				CumNetForeignFlowRpB: flowB,
				TurnoverRpB:          turnB,
				FlowRatioPct:         rec.FlowIntensityPct,
				AccumulationScore:    rec.CompounderScore,
				Signal:               sig,
				Priority:             prio,
				DCAVerdict:           rec.DCAVerdict,
			}
		}

		resp := map[string]any{
			"signal":            "STEALTH_ACCUMULATION",
			"smart_money_delta": totalSmartMoney,
			"summary": map[string]any{
				"on_date":                   time.Now().Format("2006-01-02"),
				"smart_money_turnover_rp_b": totalSmartMoney,
				"retail_turnover_rp_b":      math.Max(0, totalTurnover-totalSmartMoney),
				"smart_money_delta":         totalSmartMoney,
			},
			"anomalies": anomalies,
		}
		writeJSON(w, http.StatusOK, resp)
	})

	mux.HandleFunc("GET /api/foreign-flow", func(w http.ResponseWriter, r *http.Request) {
		topN := 25
		if t := r.URL.Query().Get("top_n"); t != "" {
			if n, err := strconv.Atoi(t); err == nil {
				topN = n
			}
		}
		ranks, err := engine.GetForeignFlowScreen(cfg.DataDir, topN)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, http.StatusOK, ranks)
	})

	mux.HandleFunc("GET /api/signals", func(w http.ResponseWriter, r *http.Request) {
		briefingFile := filepath.Join(cfg.DataDir, "briefings", "latest.json")
		if data, err := os.ReadFile(briefingFile); err == nil {
			w.Header().Set("Content-Type", "application/json")
			w.Write(data)
			return
		}

		stealth, _ := engine.ScanStealthAccumulation(cfg.DataDir, 10)
		fflow, _ := engine.GetForeignFlowScreen(cfg.DataDir, 10)
		writeJSON(w, http.StatusOK, map[string]any{
			"status":               "ok",
			"date":                 time.Now().Format("2006-01-02"),
			"stealth_accumulation": stealth,
			"foreign_flow_top":     fflow,
		})
	})

	// 8. Knowledge Graph, Network Visualizer & UBO Power Map
	mux.HandleFunc("GET /api/graph/centrality", func(w http.ResponseWriter, r *http.Request) {
		powerFile := filepath.Join(cfg.DataDir, "power_map_export.json")
		if data, err := os.ReadFile(powerFile); err == nil {
			var parsed struct {
				Power200 any `json:"power200"`
			}
			if err := json.Unmarshal(data, &parsed); err == nil && parsed.Power200 != nil {
				writeJSON(w, http.StatusOK, parsed.Power200)
				return
			}
		}
		writeJSON(w, http.StatusOK, []any{})
	})

	mux.HandleFunc("GET /api/graph/network/{ticker}", func(w http.ResponseWriter, r *http.Request) {
		ticker := strings.ToUpper(r.PathValue("ticker"))
		dash, err := engine.LoadDashboardData(cfg.DataDir)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		var target *models.Company
		for i := range dash.Companies {
			if dash.Companies[i].Code == ticker {
				target = &dash.Companies[i]
				break
			}
		}
		if target == nil {
			http.Error(w, fmt.Sprintf("Ticker %s not found", ticker), http.StatusNotFound)
			return
		}

		type GraphNode struct {
			ID    string `json:"id"`
			Label string `json:"label"`
			Group string `json:"group"`
			Level int    `json:"level"`
			Title string `json:"title,omitempty"`
		}
		type GraphEdge struct {
			From  string `json:"from"`
			To    string `json:"to"`
			Label string `json:"label,omitempty"`
		}

		nodes := []GraphNode{
			{ID: ticker, Label: ticker + "\n" + target.Name, Group: "company", Level: 2},
		}
		edges := []GraphEdge{}

		for _, sh := range target.Shareholders {
			shID := "sh_" + strings.ReplaceAll(sh.Name, " ", "_")
			nodes = append(nodes, GraphNode{
				ID:    shID,
				Label: sh.Name,
				Group: "shareholder",
				Level: 1,
				Title: fmt.Sprintf("%.2f%% Shareholding", sh.Percentage),
			})
			edges = append(edges, GraphEdge{
				From:  shID,
				To:    ticker,
				Label: fmt.Sprintf("%.1f%%", sh.Percentage),
			})
		}

		for _, sub := range target.Subsidiaries {
			subID := "sub_" + strings.ReplaceAll(sub.Name, " ", "_")
			nodes = append(nodes, GraphNode{
				ID:    subID,
				Label: sub.Name,
				Group: "subsidiary",
				Level: 3,
				Title: fmt.Sprintf("%.2f%% Subsidiary", sub.Percentage),
			})
			edges = append(edges, GraphEdge{
				From:  ticker,
				To:    subID,
				Label: fmt.Sprintf("%.1f%%", sub.Percentage),
			})
		}

		for _, bm := range target.BoardMembers {
			bmID := "bm_" + strings.ReplaceAll(bm.Name, " ", "_")
			title := bm.Title
			if title == "" {
				title = bm.Role
			}
			nodes = append(nodes, GraphNode{
				ID:    bmID,
				Label: bm.Name,
				Group: "insider",
				Level: 1,
				Title: title,
			})
			edges = append(edges, GraphEdge{
				From:  bmID,
				To:    ticker,
				Label: title,
			})
		}

		controlling := ""
		if len(target.Shareholders) > 0 {
			controlling = target.Shareholders[0].Name
		}

		writeJSON(w, http.StatusOK, map[string]any{
			"ticker": ticker,
			"nodes":  nodes,
			"edges":  edges,
			"summary": map[string]any{
				"controlling_owner": controlling,
				"total_nodes":       len(nodes),
				"total_edges":       len(edges),
			},
		})
	})

	mux.HandleFunc("GET /api/graph/cross-holdings", func(w http.ResponseWriter, r *http.Request) {
		dash, _ := engine.LoadDashboardData(cfg.DataDir)
		type CrossHolding struct {
			SourceTicker string  `json:"source_ticker"`
			TargetTicker string  `json:"target_ticker"`
			Relationship string  `json:"relationship"`
			Percentage   float64 `json:"percentage"`
		}
		var holdings []CrossHolding
		codeMap := make(map[string]bool)
		for _, c := range dash.Companies {
			codeMap[c.Code] = true
		}
		for _, c := range dash.Companies {
			for _, sub := range c.Subsidiaries {
				upperSub := strings.ToUpper(sub.Name)
				for otherCode := range codeMap {
					if strings.Contains(upperSub, otherCode) && otherCode != c.Code {
						holdings = append(holdings, CrossHolding{
							SourceTicker: c.Code,
							TargetTicker: otherCode,
							Relationship: "Subsidiary Cross-Holding",
							Percentage:   sub.Percentage,
						})
					}
				}
			}
		}
		writeJSON(w, http.StatusOK, holdings)
	})

	mux.HandleFunc("GET /api/stock/{ticker}/blocks", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, []any{})
	})

	mux.HandleFunc("GET /api/graph/ubo/{ticker}", func(w http.ResponseWriter, r *http.Request) {
		ticker := strings.ToUpper(r.PathValue("ticker"))
		dash, _ := engine.LoadDashboardData(cfg.DataDir)
		for _, c := range dash.Companies {
			if c.Code == ticker {
				writeJSON(w, http.StatusOK, map[string]any{
					"ticker":       ticker,
					"name":         c.Name,
					"shareholders": c.Shareholders,
					"subsidiaries": c.Subsidiaries,
					"board":        c.BoardMembers,
				})
				return
			}
		}
		http.Error(w, fmt.Sprintf("Ticker %s not found", ticker), http.StatusNotFound)
	})

	// 9. System Ingestion Status
	mux.HandleFunc("GET /api/system/ingestion-status", func(w http.ResponseWriter, r *http.Request) {
		tsDir := filepath.Join(cfg.DataDir, "timeseries")
		datasets := []string{"stock_summary", "broker_summary", "index_summary"}
		summary := make(map[string]any)
		for _, ds := range datasets {
			pDir := filepath.Join(tsDir, ds)
			entries, _ := os.ReadDir(pDir)
			dates := make([]string, 0, len(entries))
			for _, e := range entries {
				if strings.HasPrefix(e.Name(), "date=") {
					dates = append(dates, strings.TrimSuffix(strings.TrimPrefix(e.Name(), "date="), ".parquet"))
				}
			}
			summary[ds] = map[string]any{
				"total_partitions": len(dates),
				"dates_sample":     dates[:min(5, len(dates))],
			}
		}
		writeJSON(w, http.StatusOK, summary)
	})

	// 8. WebSocket Stream
	mux.HandleFunc("/ws/stream", func(w http.ResponseWriter, r *http.Request) {
		opts := &websocket.AcceptOptions{
			OriginPatterns: []string{"*"},
		}
		conn, err := websocket.Accept(w, r, opts)
		if err != nil {
			log.Printf("WebSocket accept error: %v", err)
			return
		}
		defer conn.CloseNow()

		hub.Add(conn)
		defer hub.Remove(conn)

		// Initial connection greeting
		_ = conn.Write(r.Context(), websocket.MessageText, []byte(`{"type":"connected","service":"idx-microservice-stream"}`))

		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-r.Context().Done():
				return
			case <-ticker.C:
				heartbeat := map[string]any{
					"type":              "heartbeat",
					"status":            "alive",
					"timestamp":         time.Now().Unix(),
					"connected_clients": hub.Count(),
				}
				hbBytes, _ := json.Marshal(heartbeat)
				if err := conn.Write(r.Context(), websocket.MessageText, hbBytes); err != nil {
					return
				}
			}
		}
	})

	// Broadcast endpoint
	mux.HandleFunc("POST /api/broadcast", func(w http.ResponseWriter, r *http.Request) {
		body, err := os.ReadFile(r.URL.Path)
		if err == nil && len(body) > 0 {
			hub.Broadcast(r.Context(), body)
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "broadcasted"})
	})

	return corsMiddleware(mux)
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "*")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
