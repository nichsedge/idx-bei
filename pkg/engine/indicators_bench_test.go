package engine_test

import (
	"math/rand"
	"testing"

	"github.com/nichsedge/idx-bei/pkg/engine"
	"github.com/nichsedge/idx-bei/pkg/models"
)

func generateDummyRecords(n int) []models.StockRecord {
	records := make([]models.StockRecord, n)
	price := 5000.0
	r := rand.New(rand.NewSource(42))
	for i := 0; i < n; i++ {
		change := (r.Float64() - 0.48) * 100
		price += change
		if price < 50 {
			price = 50
		}
		high := price + r.Float64()*50
		low := price - r.Float64()*50
		records[i] = models.StockRecord{
			Date:   "2026-01-01",
			Close:  price,
			Open:   price - change/2,
			High:   high,
			Low:    low,
			Volume: 1000000,
		}
	}
	return records
}

func BenchmarkComputeTechnicalIndicators(b *testing.B) {
	records := generateDummyRecords(1000)
	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		// Clone shallow records
		cp := make([]models.StockRecord, len(records))
		copy(cp, records)
		engine.ComputeTechnicalIndicators(cp)
	}
}
