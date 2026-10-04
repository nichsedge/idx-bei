package ingest

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"os"
	"path/filepath"
	"time"

	fhttp "github.com/bogdanfinn/fhttp"
	tls_client "github.com/bogdanfinn/tls-client"
	"github.com/bogdanfinn/tls-client/profiles"
)

const (
	DefaultBaseURL = "https://www.idx.co.id/primary"
	DefaultOpenFX  = "https://open.er-api.com/v6/latest/USD"
)

type EndpointConfig struct {
	Name    string
	Path    string
	DataKey string
}

var Endpoints = []EndpointConfig{
	{Name: "stock_summary", Path: "/TradingSummary/GetStockSummary", DataKey: "data"},
	{Name: "broker_summary", Path: "/TradingSummary/GetBrokerSummary", DataKey: "data"},
	{Name: "index_summary", Path: "/TradingSummary/GetIndexSummary", DataKey: "data"},
}

type SyncSummary struct {
	Date       string         `json:"date"`
	Timestamp  string         `json:"timestamp"`
	Results    map[string]int `json:"results"`
	UsdIdrRate float64        `json:"usd_idr_rate,omitempty"`
	Errors     []string       `json:"errors,omitempty"`
}

type SyncOptions struct {
	Date       string
	DataDir    string
	WebhookURL string
	Delay      float64
	Retries    int
}

// RunDailySync runs the full uTLS ingestion for the target date.
func RunDailySync(opts SyncOptions) (*SyncSummary, error) {
	if opts.DataDir == "" {
		opts.DataDir = "data"
	}
	if opts.Delay <= 0 {
		opts.Delay = 1.0
	}
	if opts.Retries <= 0 {
		opts.Retries = 3
	}
	date := opts.Date
	if date == "" {
		date = time.Now().Format("20060102")
	}
	if len(date) != 8 {
		return nil, fmt.Errorf("invalid date format: %q, expected YYYYMMDD", date)
	}
	dateISO := fmt.Sprintf("%s-%s-%s", date[0:4], date[4:6], date[6:8])

	log.Printf("== IDX-BEI Standalone Go Sync ==")
	log.Printf("Target Date: %s (%s)", date, dateISO)
	log.Printf("Data Dir:    %s", opts.DataDir)

	client, err := CreateTLSClient()
	if err != nil {
		return nil, fmt.Errorf("failed to initialize TLS client: %w", err)
	}

	summary := &SyncSummary{
		Date:      dateISO,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Results:   make(map[string]int),
		Errors:    make([]string, 0),
	}

	// 1. Ingest trading summary endpoints
	for _, ep := range Endpoints {
		log.Printf("[%s] Fetching trading summary for %s...", ep.Name, date)
		url := fmt.Sprintf("%s%s?date=%s&start=0&length=9999", DefaultBaseURL, ep.Path, date)

		records, err := FetchWithRetry(client, url, opts.Retries, time.Duration(opts.Delay*float64(time.Second)))
		if err != nil {
			msg := fmt.Sprintf("%s: fetch error: %v", ep.Name, err)
			log.Printf("ERROR: %s", msg)
			summary.Errors = append(summary.Errors, msg)
			continue
		}

		count := len(records)
		summary.Results[ep.Name] = count

		if count == 0 {
			log.Printf("[%s] No records returned for %s (weekend/market holiday?)", ep.Name, dateISO)
			continue
		}

		// Save JSON partition: data/timeseries/<dataset>/date=YYYY-MM-DD.json
		tsDir := filepath.Join(opts.DataDir, "timeseries", ep.Name)
		if err := os.MkdirAll(tsDir, 0755); err != nil {
			log.Printf("ERROR creating directory %s: %v", tsDir, err)
			summary.Errors = append(summary.Errors, fmt.Sprintf("%s: mkdir error: %v", ep.Name, err))
			continue
		}

		partitionFile := filepath.Join(tsDir, fmt.Sprintf("date=%s.json", dateISO))
		if err := WriteJSONAtomic(partitionFile, records); err != nil {
			log.Printf("ERROR writing partition %s: %v", partitionFile, err)
			summary.Errors = append(summary.Errors, fmt.Sprintf("%s: write error: %v", ep.Name, err))
			continue
		}

		log.Printf("[%s] Wrote %d records to %s", ep.Name, count, partitionFile)
		time.Sleep(time.Duration(opts.Delay * float64(time.Second)))
	}

	// 2. Fetch USD/IDR exchange rate
	rate, err := FetchUSDIDRRate()
	if err != nil {
		log.Printf("WARN: Failed to refresh USD/IDR exchange rate: %v", err)
	} else {
		summary.UsdIdrRate = rate
		rateFile := filepath.Join(opts.DataDir, "usd_idr_rate.json")
		ratePayload := map[string]any{
			"rate":      rate,
			"timestamp": time.Now().Unix(),
			"source":    "open.er-api.com (go-idx-sync)",
		}
		if err := WriteJSONAtomic(rateFile, ratePayload); err != nil {
			log.Printf("WARN: Failed to save %s: %v", rateFile, err)
		} else {
			log.Printf("USD/IDR rate updated: %.2f -> %s", rate, rateFile)
		}
	}

	// 3. Optional Webhook
	if opts.WebhookURL != "" {
		_ = SendDiscordWebhook(opts.WebhookURL, *summary)
	}

	return summary, nil
}

func CreateTLSClientWithProfile(p profiles.ClientProfile) (tls_client.HttpClient, error) {
	jar := tls_client.NewCookieJar()
	options := []tls_client.HttpClientOption{
		tls_client.WithTimeoutSeconds(30),
		tls_client.WithClientProfile(p),
		tls_client.WithCookieJar(jar),
	}
	return tls_client.NewHttpClient(tls_client.NewNoopLogger(), options...)
}

func CreateTLSClient() (tls_client.HttpClient, error) {
	return CreateTLSClientWithProfile(profiles.Safari_16_0)
}

func FetchWithRetry(client tls_client.HttpClient, url string, maxRetries int, delay time.Duration) ([]map[string]any, error) {
	clientProfiles := []profiles.ClientProfile{
		profiles.Chrome_120,
		profiles.Chrome_124,
		profiles.Safari_16_0,
	}

	var lastErr error
	currentClient := client
	for attempt := 0; attempt <= maxRetries; attempt++ {
		req, err := fhttp.NewRequest("GET", url, nil)
		if err != nil {
			return nil, err
		}

		req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
		req.Header.Set("Accept", "application/json, text/plain, */*")
		req.Header.Set("Accept-Language", "en-US,en;q=0.9")
		req.Header.Set("Referer", "https://www.idx.co.id/")

		resp, err := currentClient.Do(req)
		if err != nil {
			lastErr = err
			backoff := time.Duration(float64(attempt+1)*1.5+rand.Float64()) * time.Second
			log.Printf("Request error: %v. Retrying in %v...", err, backoff)
			time.Sleep(backoff)
			continue
		}

		bodyBytes, err := io.ReadAll(resp.Body)
		resp.Body.Close()

		if err != nil {
			lastErr = err
			continue
		}

		if resp.StatusCode == 200 {
			var parsed struct {
				Data []map[string]any `json:"data"`
			}
			if err := json.Unmarshal(bodyBytes, &parsed); err != nil {
				return nil, fmt.Errorf("failed to parse JSON response: %w", err)
			}
			return parsed.Data, nil
		}

		if resp.StatusCode == 403 || resp.StatusCode == 429 || resp.StatusCode >= 500 {
			nextProfile := clientProfiles[attempt%len(clientProfiles)]
			newClient, err := CreateTLSClientWithProfile(nextProfile)
			if err == nil {
				currentClient = newClient
			}
			backoff := time.Duration(float64(attempt+1)*2.0+rand.Float64()) * time.Second
			log.Printf("HTTP %d for %s (rotating TLS profile, retrying in %v...)", resp.StatusCode, url, backoff)
			time.Sleep(backoff)
			lastErr = fmt.Errorf("HTTP %d", resp.StatusCode)
			continue
		}

		return nil, fmt.Errorf("unhandled HTTP %d from %s", resp.StatusCode, url)
	}

	return nil, fmt.Errorf("max retries exceeded: %w", lastErr)
}

func FetchUSDIDRRate() (float64, error) {
	client := &http.Client{Timeout: 10 * time.Second}
	req, err := http.NewRequest("GET", DefaultOpenFX, nil)
	if err != nil {
		return 0, err
	}
	req.Header.Set("User-Agent", "IDX-BEI Termux Syncer/1.0")

	resp, err := client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return 0, fmt.Errorf("HTTP %d from exchange API", resp.StatusCode)
	}

	var result struct {
		Rates map[string]float64 `json:"rates"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, err
	}

	rate, ok := result.Rates["IDR"]
	if !ok || rate < 10000 || rate > 35000 {
		return 0, fmt.Errorf("invalid USD/IDR rate received: %v", rate)
	}
	return rate, nil
}

func WriteJSONAtomic(path string, data any) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	tmpPath := path + ".tmp"
	f, err := os.Create(tmpPath)
	if err != nil {
		return err
	}

	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	if err := enc.Encode(data); err != nil {
		f.Close()
		os.Remove(tmpPath)
		return err
	}

	if err := f.Close(); err != nil {
		os.Remove(tmpPath)
		return err
	}

	return os.Rename(tmpPath, path)
}

func SendDiscordWebhook(webhookURL string, summary SyncSummary) error {
	fields := []map[string]any{
		{"name": "Trading Date", "value": summary.Date, "inline": true},
		{"name": "USD/IDR Rate", "value": fmt.Sprintf("Rp %.2f", summary.UsdIdrRate), "inline": true},
	}
	for ep, count := range summary.Results {
		fields = append(fields, map[string]any{
			"name":   ep,
			"value":  fmt.Sprintf("%d records", count),
			"inline": true,
		})
	}
	payload := map[string]any{
		"username": "IDX-BEI Ingestion Bot",
		"embeds": []map[string]any{
			{
				"title":       "IDX-BEI Daily Ingestion Complete",
				"color":       3066993,
				"fields":      fields,
				"timestamp":   summary.Timestamp,
			},
		},
	}
	jsonBytes, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	resp, err := http.Post(webhookURL, "application/json", bytes.NewBuffer(jsonBytes))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return nil
}
