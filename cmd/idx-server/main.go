package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/nichsedge/idx-bei/pkg/api"
)

func main() {
	hostFlag := flag.String("host", "127.0.0.1", "Host interface to bind to")
	portFlag := flag.Int("port", 8000, "Port to listen on")
	dataDirFlag := flag.String("data-dir", "data", "Base data directory")
	flag.Parse()

	// Resolve absolute path to dataDir if needed
	dataDir := *dataDirFlag
	if !filepath.IsAbs(dataDir) {
		cwd, _ := os.Getwd()
		candidate := filepath.Join(cwd, dataDir)
		if _, err := os.Stat(candidate); err == nil {
			dataDir = candidate
		} else {
			// Try checking if we are inside cmd or bin
			parentData := filepath.Join(cwd, "..", "..", dataDir)
			if _, err := os.Stat(parentData); err == nil {
				dataDir = parentData
			}
		}
	}

	cfg := api.ServerConfig{
		Host:    *hostFlag,
		Port:    *portFlag,
		DataDir: dataDir,
	}

	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	log.Printf("=== Starting IDX-BEI Microservice Server (Go) on http://%s ===", addr)
	log.Printf("  • Web Dashboard:  http://localhost:%d/", cfg.Port)
	log.Printf("  • REST API:       http://localhost:%d/health", cfg.Port)
	log.Printf("  • WebSocket:      ws://localhost:%d/ws/stream", cfg.Port)
	log.Printf("  • Data Dir:       %s", cfg.DataDir)

	router := api.NewRouter(cfg)
	srv := &http.Server{
		Addr:              addr,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       120 * time.Second,
	}
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server failed: %v", err)
	}
}
