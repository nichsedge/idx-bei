package main

import (
	"flag"
	"fmt"
	"log"
	"time"

	"github.com/nichsedge/idx-bei/pkg/ingest"
)

func main() {
	now := time.Now()
	defaultDate := now.Format("20060102")

	dateFlag := flag.String("date", defaultDate, "Target date in YYYYMMDD format (e.g. 20260401)")
	dataDirFlag := flag.String("data-dir", "data", "Base data directory (e.g. ./data)")
	webhookFlag := flag.String("webhook", "", "Optional Discord/Slack webhook URL for alerts")
	delayFlag := flag.Float64("delay", 1.0, "Delay in seconds between requests")
	retriesFlag := flag.Int("retries", 3, "Max retry attempts per endpoint")
	flag.Parse()

	opts := ingest.SyncOptions{
		Date:       *dateFlag,
		DataDir:    *dataDirFlag,
		WebhookURL: *webhookFlag,
		Delay:      *delayFlag,
		Retries:    *retriesFlag,
	}

	summary, err := ingest.RunDailySync(opts)
	if err != nil {
		log.Fatalf("Ingestion failed: %v", err)
	}

	fmt.Println("Ingestion finished successfully:")
	for ep, count := range summary.Results {
		fmt.Printf("  • %-16s: %d records\n", ep, count)
	}
	if summary.UsdIdrRate > 0 {
		fmt.Printf("  • USD/IDR Rate    : Rp %.2f\n", summary.UsdIdrRate)
	}
}
