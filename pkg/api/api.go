package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/coder/websocket"
	"github.com/nichsedge/idx-bei/pkg/engine"
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

	// 5. Signals & Intelligence Briefing
	mux.HandleFunc("GET /api/signals", func(w http.ResponseWriter, r *http.Request) {
		briefingFile := filepath.Join(cfg.DataDir, "briefings", "latest.json")
		if data, err := os.ReadFile(briefingFile); err == nil {
			w.Header().Set("Content-Type", "application/json")
			w.Write(data)
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{
			"status":  "ok",
			"message": "no pre-generated briefing, daily partitions available",
		})
	})

	// 6. Knowledge Graph & UBO Power Map
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

	// 7. System Ingestion Status
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
