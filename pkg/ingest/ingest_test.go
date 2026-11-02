package ingest

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestMapToStockRow(t *testing.T) {
	record := map[string]any{
		"Date":                "2026-09-18",
		"StockCode":           "BBCA",
		"StockName":           "Bank Central Asia Tbk.",
		"Previous":            6400.0,
		"OpenPrice":           6425.0,
		"High":                6475.0,
		"Low":                 6300.0,
		"Close":               6300.0,
		"Change":              -100.0,
		"Volume":              125000000.0,
		"Value":               800000000000.0,
		"Frequency":           25000.0,
		"ForeignSell":         45000000.0,
		"ForeignBuy":          55000000.0,
		"NonRegularVolume":    1000000.0,
		"NonRegularValue":     6300000000.0,
		"NonRegularFrequency": 10.0,
	}

	row := mapToStockRow(record, "2026-09-18")

	if row.StockCode != "BBCA" {
		t.Errorf("expected stock code BBCA, got %s", row.StockCode)
	}
	if row.Close != 6300.0 {
		t.Errorf("expected close 6300, got %f", row.Close)
	}
	if row.ForeignBuy != 55000000.0 {
		t.Errorf("expected foreign buy 55000000, got %f", row.ForeignBuy)
	}
	if row.ForeignSell != 45000000.0 {
		t.Errorf("expected foreign sell 45000000, got %f", row.ForeignSell)
	}
}

func TestEndpointsConfig(t *testing.T) {
	if len(Endpoints) != 3 {
		t.Fatalf("expected 3 endpoints, got %d", len(Endpoints))
	}
	names := map[string]bool{}
	for _, ep := range Endpoints {
		names[ep.Name] = true
	}
	for _, expected := range []string{"stock_summary", "broker_summary", "index_summary"} {
		if !names[expected] {
			t.Errorf("expected endpoint %s not found", expected)
		}
	}
}

func TestFetchUSDIDRRateFallback(t *testing.T) {
	primary := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer primary.Close()

	fallback := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"amount":1.0,"base":"USD","date":"2026-10-30","rates":{"IDR":16250.5}}`))
	}))
	defer fallback.Close()

	rate, source, err := FetchUSDIDRRateFromSources([]string{primary.URL, fallback.URL})
	if err != nil {
		t.Fatalf("expected fallback to succeed, got error: %v", err)
	}
	if rate != 16250.5 {
		t.Errorf("expected rate 16250.5, got %f", rate)
	}
	if source != sourceHost(fallback.URL) {
		t.Errorf("expected source %s, got %s", sourceHost(fallback.URL), source)
	}
}

func TestFetchUSDIDRRatePrimarySuccess(t *testing.T) {
	primary := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"result":"success","rates":{"IDR":16100.0}}`))
	}))
	defer primary.Close()

	fallbackHit := false
	fallback := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fallbackHit = true
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer fallback.Close()

	rate, source, err := FetchUSDIDRRateFromSources([]string{primary.URL, fallback.URL})
	if err != nil {
		t.Fatalf("expected primary to succeed, got error: %v", err)
	}
	if rate != 16100.0 {
		t.Errorf("expected rate 16100.0, got %f", rate)
	}
	if source != sourceHost(primary.URL) {
		t.Errorf("expected source %s, got %s", sourceHost(primary.URL), source)
	}
	if fallbackHit {
		t.Errorf("fallback server should not have been called when primary succeeds")
	}
}

func TestFetchUSDIDRRateAllFail(t *testing.T) {
	s1 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
	}))
	defer s1.Close()

	s2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer s2.Close()

	_, _, err := FetchUSDIDRRateFromSources([]string{s1.URL, s2.URL})
	if err == nil {
		t.Fatal("expected error when all sources fail, got nil")
	}

	errStr := err.Error()
	if !strings.Contains(errStr, sourceHost(s1.URL)) || !strings.Contains(errStr, sourceHost(s2.URL)) {
		t.Errorf("expected combined error to mention both hosts, got: %s", errStr)
	}
}

func TestFetchUSDIDRRateSanityBounds(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"rates":{"IDR":5000.0}}`)) // Out of bounds (<10000)
	}))
	defer server.Close()

	_, _, err := FetchUSDIDRRateFromSources([]string{server.URL})
	if err == nil {
		t.Fatal("expected rate below 10,000 to be rejected as invalid, got nil error")
	}
}
