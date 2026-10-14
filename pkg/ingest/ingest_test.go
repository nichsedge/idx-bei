package ingest

import (
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
