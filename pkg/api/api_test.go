package api_test

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/nichsedge/idx-bei/pkg/api"
)

func newTestRouter() http.Handler {
	cfg := api.ServerConfig{
		DataDir: filepath.Join("..", "..", "data"),
	}
	return api.NewRouter(cfg)
}

func TestHealthEndpoint(t *testing.T) {
	router := newTestRouter()

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "idx-bei-api") {
		t.Fatalf("expected body to contain idx-bei-api, got: %s", w.Body.String())
	}
}

func TestDividendEndpoints(t *testing.T) {
	router := newTestRouter()

	// 1. Screen
	req := httptest.NewRequest("GET", "/api/dividend?min_yield=1.0&limit=5", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200 for dividend screen, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "Ticker") {
		t.Fatalf("expected dividend screen to contain Ticker fields, got: %s", w.Body.String())
	}

	// 2. Ticker detail (BBCA)
	reqDetail := httptest.NewRequest("GET", "/api/dividend/BBCA", nil)
	wDetail := httptest.NewRecorder()
	router.ServeHTTP(wDetail, reqDetail)

	if wDetail.Code != http.StatusOK {
		t.Fatalf("expected status 200 for BBCA dividend, got %d: %s", wDetail.Code, wDetail.Body.String())
	}
	if !strings.Contains(wDetail.Body.String(), "BBCA") {
		t.Fatalf("expected detail to contain BBCA, got: %s", wDetail.Body.String())
	}
}

func TestBacktestEndpoints(t *testing.T) {
	router := newTestRouter()

	// 1. GET backtest
	reqGet := httptest.NewRequest("GET", "/api/backtest?strategy=compounder&holding_days=10&top_n=5", nil)
	wGet := httptest.NewRecorder()
	router.ServeHTTP(wGet, reqGet)

	if wGet.Code != http.StatusOK {
		t.Fatalf("expected status 200 for GET backtest, got %d: %s", wGet.Code, wGet.Body.String())
	}
	if !strings.Contains(wGet.Body.String(), "metrics") {
		t.Fatalf("expected backtest response to contain metrics, got: %s", wGet.Body.String())
	}

	// 2. POST backtest
	payload := []byte(`{"strategy":"foreign_flow","holding_days":15,"top_n":5,"stop_loss_pct":5.0,"take_profit_pct":15.0}`)
	reqPost := httptest.NewRequest("POST", "/api/backtest", bytes.NewReader(payload))
	reqPost.Header.Set("Content-Type", "application/json")
	wPost := httptest.NewRecorder()
	router.ServeHTTP(wPost, reqPost)

	if wPost.Code != http.StatusOK {
		t.Fatalf("expected status 200 for POST backtest, got %d: %s", wPost.Code, wPost.Body.String())
	}
	if !strings.Contains(wPost.Body.String(), "equity_curve") {
		t.Fatalf("expected POST backtest response to contain equity_curve, got: %s", wPost.Body.String())
	}
}

func TestStealthAndForeignFlowEndpoints(t *testing.T) {
	router := newTestRouter()

	// 1. Stealth accumulation
	reqStealth := httptest.NewRequest("GET", "/api/stealth-accumulation?limit=10", nil)
	wStealth := httptest.NewRecorder()
	router.ServeHTTP(wStealth, reqStealth)

	if wStealth.Code != http.StatusOK {
		t.Fatalf("expected status 200 for stealth accumulation, got %d: %s", wStealth.Code, wStealth.Body.String())
	}
	if !strings.Contains(wStealth.Body.String(), "anomalies") {
		t.Fatalf("expected stealth response to contain anomalies, got: %s", wStealth.Body.String())
	}

	// 2. Foreign flow
	reqFlow := httptest.NewRequest("GET", "/api/foreign-flow?top_n=10", nil)
	wFlow := httptest.NewRecorder()
	router.ServeHTTP(wFlow, reqFlow)

	if wFlow.Code != http.StatusOK {
		t.Fatalf("expected status 200 for foreign flow, got %d: %s", wFlow.Code, wFlow.Body.String())
	}

	// 3. Dynamic signals briefing
	reqSig := httptest.NewRequest("GET", "/api/signals", nil)
	wSig := httptest.NewRecorder()
	router.ServeHTTP(wSig, reqSig)

	if wSig.Code != http.StatusOK {
		t.Fatalf("expected status 200 for signals, got %d: %s", wSig.Code, wSig.Body.String())
	}
}

func TestGraphEndpoints(t *testing.T) {
	router := newTestRouter()

	// 1. Network graph for BBCA
	reqNet := httptest.NewRequest("GET", "/api/graph/network/BBCA", nil)
	wNet := httptest.NewRecorder()
	router.ServeHTTP(wNet, reqNet)

	if wNet.Code != http.StatusOK {
		t.Fatalf("expected status 200 for BBCA network graph, got %d: %s", wNet.Code, wNet.Body.String())
	}
	if !strings.Contains(wNet.Body.String(), "nodes") || !strings.Contains(wNet.Body.String(), "edges") {
		t.Fatalf("expected network graph to contain nodes and edges, got: %s", wNet.Body.String())
	}

	// 2. Cross holdings
	reqCross := httptest.NewRequest("GET", "/api/graph/cross-holdings", nil)
	wCross := httptest.NewRecorder()
	router.ServeHTTP(wCross, reqCross)

	if wCross.Code != http.StatusOK {
		t.Fatalf("expected status 200 for cross-holdings, got %d: %s", wCross.Code, wCross.Body.String())
	}
}
