package api_test

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/nichsedge/idx-bei/pkg/api"
)

func TestHealthEndpoint(t *testing.T) {
	cfg := api.ServerConfig{
		DataDir: filepath.Join("..", "..", "data"),
	}
	router := api.NewRouter(cfg)

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}
	if !stringsContains(w.Body.String(), "idx-bei-api") {
		t.Fatalf("expected body to contain idx-bei-api, got: %s", w.Body.String())
	}
}

func stringsContains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(substr) == 0 || (len(s) > 0 && len(substr) > 0 && searchSubstr(s, substr)))
}

func searchSubstr(s, substr string) bool {
	for i := 0; i+len(substr) <= len(s); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
