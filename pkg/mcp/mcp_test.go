package mcp

import (
	"encoding/json"
	"path/filepath"
	"testing"
)

func TestMCPInitialize(t *testing.T) {
	req := JSONRPCRequest{
		JSONRPC: "2.0",
		ID:      1,
		Method:  "initialize",
	}
	resp := handleRequest("testdata", req)
	if resp.Error != nil {
		t.Fatalf("unexpected error: %v", resp.Error)
	}
	resMap, ok := resp.Result.(map[string]any)
	if !ok {
		t.Fatalf("expected map result, got %T", resp.Result)
	}
	if resMap["protocolVersion"] != "2024-11-05" {
		t.Errorf("expected protocolVersion 2024-11-05, got %v", resMap["protocolVersion"])
	}
}

func TestMCPToolsList(t *testing.T) {
	req := JSONRPCRequest{
		JSONRPC: "2.0",
		ID:      2,
		Method:  "tools/list",
	}
	resp := handleRequest("testdata", req)
	if resp.Error != nil {
		t.Fatalf("unexpected error: %v", resp.Error)
	}
	resMap, ok := resp.Result.(map[string]any)
	if !ok {
		t.Fatalf("expected map result, got %T", resp.Result)
	}
	tools, ok := resMap["tools"].([]Tool)
	if !ok || len(tools) == 0 {
		t.Fatalf("expected non-empty tools list, got %v", resMap["tools"])
	}

	foundStock := false
	for _, tool := range tools {
		if tool.Name == "idx_query_stock" {
			foundStock = true
			break
		}
	}
	if !foundStock {
		t.Errorf("idx_query_stock tool missing from tools/list")
	}
}

func TestMCPToolsCallUnknown(t *testing.T) {
	params, _ := json.Marshal(map[string]any{
		"name":      "non_existent_tool",
		"arguments": map[string]any{},
	})
	req := JSONRPCRequest{
		JSONRPC: "2.0",
		ID:      3,
		Method:  "tools/call",
		Params:  params,
	}
	resp := handleRequest("testdata", req)
	toolRes, ok := resp.Result.(ToolResult)
	if !ok {
		t.Fatalf("expected ToolResult, got %T", resp.Result)
	}
	if !toolRes.IsError {
		t.Errorf("expected IsError=true for unknown tool")
	}
}

func TestMCPToolsCallMissingArgs(t *testing.T) {
	params, _ := json.Marshal(map[string]any{
		"name":      "idx_query_stock",
		"arguments": map[string]any{},
	})
	req := JSONRPCRequest{
		JSONRPC: "2.0",
		ID:      4,
		Method:  "tools/call",
		Params:  params,
	}
	resp := handleRequest("testdata", req)
	toolRes, ok := resp.Result.(ToolResult)
	if !ok {
		t.Fatalf("expected ToolResult, got %T", resp.Result)
	}
	if !toolRes.IsError {
		t.Errorf("expected IsError=true for missing ticker arg")
	}
}

func TestMCPToolsCallCompounders(t *testing.T) {
	dataDir := filepath.Join("..", "..", "data")
	params, _ := json.Marshal(map[string]any{
		"name": "idx_screen_compounders",
		"arguments": map[string]any{
			"top":       5,
			"min_score": 60.0,
		},
	})
	req := JSONRPCRequest{
		JSONRPC: "2.0",
		ID:      5,
		Method:  "tools/call",
		Params:  params,
	}
	resp := handleRequest(dataDir, req)
	toolRes, ok := resp.Result.(ToolResult)
	if !ok {
		t.Fatalf("expected ToolResult, got %T", resp.Result)
	}
	if toolRes.IsError {
		t.Fatalf("unexpected error in compounders screen: %v", toolRes.Content)
	}
	if len(toolRes.Content) == 0 || toolRes.Content[0].Text == "" {
		t.Errorf("expected non-empty content in tool result")
	}
}

func TestMCPMethodNotFound(t *testing.T) {
	req := JSONRPCRequest{
		JSONRPC: "2.0",
		ID:      6,
		Method:  "invalid/method",
	}
	resp := handleRequest("testdata", req)
	if resp.Error == nil {
		t.Fatalf("expected error for invalid method, got nil")
	}
	if resp.Error.Code != -32601 {
		t.Errorf("expected error code -32601, got %d", resp.Error.Code)
	}
}
