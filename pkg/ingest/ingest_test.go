package ingest

import (
	"net/http"
	"net/http/httptest"
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

func TestFetchUSDIDRRateFallsBack(t *testing.T) {
	failing := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer failing.Close()
	working := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"result":"success","base_code":"USD","rates":{"IDR":16250.5}}`))
	}))
	defer working.Close()

	orig := usdIDRSources
	defer func() { usdIDRSources = orig }()

	usdIDRSources = []string{failing.URL, working.URL}
	rate, source, err := FetchUSDIDRRate()
	if err != nil {
		t.Fatalf("expected fallback to succeed, got %v", err)
	}
	if rate != 16250.5 {
		t.Errorf("expected 16250.5, got %f", rate)
	}
	if source != sourceHost(working.URL) {
		t.Errorf("expected source %s, got %s", sourceHost(working.URL), source)
	}

	usdIDRSources = []string{failing.URL, failing.URL}
	if _, _, err := FetchUSDIDRRate(); err == nil {
		t.Error("expected error when all sources fail")
	}
}
