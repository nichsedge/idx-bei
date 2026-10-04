package engine_test

import (
	"path/filepath"
	"testing"

	"github.com/nichsedge/idx-bei/pkg/engine"
)

func TestGetCompounderScreen(t *testing.T) {
	dataDir := filepath.Join("..", "..", "data")
	res, err := engine.GetCompounderScreen(dataDir, 50.0, true, "", 10)
	if err != nil {
		t.Fatalf("failed to screen compounders: %v", err)
	}
	if len(res) == 0 {
		t.Fatalf("expected non-empty compounder results")
	}
	t.Logf("Top compounder: %s (%s) Score: %.2f", res[0].Code, res[0].Name, res[0].CompounderScore)
}

func TestGetStockData(t *testing.T) {
	dataDir := filepath.Join("..", "..", "data")
	records, latest, err := engine.GetStockData(dataDir, "BBCA", 10)
	if err != nil {
		t.Fatalf("failed to get stock data for BBCA: %v", err)
	}
	if len(records) == 0 || latest == nil {
		t.Fatalf("expected non-empty BBCA records")
	}
	t.Logf("BBCA records: %d, latest date: %s, close: %.2f", len(records), latest.Date, latest.Close)
	if latest.RSI14 != nil {
		t.Logf("BBCA latest RSI14: %.2f", *latest.RSI14)
	}
	if latest.EMA20 != nil {
		t.Logf("BBCA latest EMA20: %.2f", *latest.EMA20)
	}
}
