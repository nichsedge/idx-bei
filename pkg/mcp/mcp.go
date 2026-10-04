package mcp

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/nichsedge/idx-bei/pkg/engine"
)

type JSONRPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      any             `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type JSONRPCResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      any         `json:"id"`
	Result  any         `json:"result,omitempty"`
	Error   *RPCError   `json:"error,omitempty"`
}

type RPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type Tool struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	InputSchema any    `json:"inputSchema"`
}

type TextContent struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type ToolResult struct {
	Content []TextContent `json:"content"`
	IsError bool          `json:"isError,omitempty"`
}

var serverTools = []Tool{
	{
		Name:        "idx_query_stock",
		Description: "Query historical OHLCV, Net Foreign Flow, and technical indicators (RSI-14, EMA-20/50, Bollinger Bands) for a stock ticker.",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"ticker": map[string]any{"type": "string", "description": "4-letter IDX stock code, e.g. 'BBCA', 'BMRI', 'ASII'"},
				"limit":  map[string]any{"type": "integer", "description": "Number of recent trading sessions to return (default: 20)"},
			},
			"required": []string{"ticker"},
		},
	},
	{
		Name:        "idx_screen_compounders",
		Description: "Screen top institutional DCA compounders with forensic anti-value-trap filters, Justified PBV, and ROE metrics.",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"top":          map[string]any{"type": "integer", "description": "Number of top compounders to return (default: 15)"},
				"min_score":    map[string]any{"type": "number", "description": "Minimum compounder score threshold (default: 60.0)"},
				"show_traps":   map[string]any{"type": "boolean", "description": "Whether to include identified accounting value traps"},
			},
		},
	},
	{
		Name:        "idx_analyze_dividend",
		Description: "Perform quantitative dividend decision analysis: Net yield, Dividend Payout Ratio (DPR), Ex-Date Trap Risk Score (0-100), and Buy/Hold/Sell recommendation.",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"ticker": map[string]any{"type": "string", "description": "4-letter IDX stock code, e.g. 'PTBA', 'BBCA', 'ITMG'"},
			},
			"required": []string{"ticker"},
		},
	},
	{
		Name:        "idx_screen_dividends",
		Description: "Scan and rank all IDX dividend opportunities by yield and Ex-Date trap risk.",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"min_yield": map[string]any{"type": "number", "description": "Minimum dividend yield percentage (default: 4.0)"},
				"limit":     map[string]any{"type": "integer", "description": "Maximum number of stocks to return (default: 15)"},
			},
		},
	},
	{
		Name:        "idx_get_stealth_accumulation",
		Description: "Scan for stealth institutional accumulation where smart money / foreigners are buying heavily while price is consolidating.",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"top": map[string]any{"type": "integer", "description": "Number of candidates to return (default: 10)"},
			},
		},
	},
	{
		Name:        "idx_backtest_strategy",
		Description: "Simulate holding returns, win rate, Sharpe ratio, and drawdowns for quantitative strategies ('foreign_flow', 'composite_alpha').",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"strategy":     map[string]any{"type": "string", "description": "'foreign_flow' or 'composite_alpha'"},
				"holding_days": map[string]any{"type": "integer", "description": "Holding period in sessions (default: 20)"},
				"stop_loss":    map[string]any{"type": "number", "description": "Stop loss percentage threshold (optional)"},
				"take_profit":  map[string]any{"type": "number", "description": "Take profit percentage threshold (optional)"},
			},
		},
	},
	{
		Name:        "idx_get_peers",
		Description: "Find peer companies operating in the same sector or industry for relative valuation comparison.",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"ticker": map[string]any{"type": "string", "description": "4-letter IDX stock code"},
			},
			"required": []string{"ticker"},
		},
	},
}

// ServeStdio starts the stdio JSON-RPC 2.0 Model Context Protocol server.
func ServeStdio(dataDir string) error {
	reader := bufio.NewReader(os.Stdin)
	for {
		line, err := reader.ReadBytes('\n')
		if err != nil {
			if err == io.EOF {
				return nil
			}
			return err
		}

		if len(strings.TrimSpace(string(line))) == 0 {
			continue
		}

		var req JSONRPCRequest
		if err := json.Unmarshal(line, &req); err != nil {
			continue
		}

		resp := handleRequest(dataDir, req)
		out, err := json.Marshal(resp)
		if err == nil {
			fmt.Printf("%s\n", out)
		}
	}
}

func handleRequest(dataDir string, req JSONRPCRequest) JSONRPCResponse {
	switch req.Method {
	case "initialize":
		return JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"protocolVersion": "2024-11-05",
				"capabilities": map[string]any{
					"tools": map[string]any{},
				},
				"serverInfo": map[string]any{
					"name":    "idx-bei-mcp",
					"version": "2.0.0",
				},
			},
		}

	case "tools/list":
		return JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"tools": serverTools,
			},
		}

	case "tools/call":
		var callParams struct {
			Name      string         `json:"name"`
			Arguments map[string]any `json:"arguments"`
		}
		if err := json.Unmarshal(req.Params, &callParams); err != nil {
			return JSONRPCResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Error:   &RPCError{Code: -32602, Message: "Invalid parameters"},
			}
		}

		res := executeTool(dataDir, callParams.Name, callParams.Arguments)
		return JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result:  res,
		}

	default:
		return JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error:   &RPCError{Code: -32601, Message: fmt.Sprintf("Method not found: %s", req.Method)},
		}
	}
}

func executeTool(dataDir, name string, args map[string]any) ToolResult {
	switch name {
	case "idx_query_stock":
		ticker, _ := args["ticker"].(string)
		if ticker == "" {
			return errorResult("ticker argument is required")
		}
		limit := 20
		if l, ok := args["limit"].(float64); ok && l > 0 {
			limit = int(l)
		}
		records, latest, err := engine.GetStockData(dataDir, ticker, limit)
		if err != nil {
			return errorResult(err.Error())
		}
		payload := map[string]any{
			"ticker":  ticker,
			"latest":  latest,
			"history": records,
		}
		return jsonResult(payload)

	case "idx_screen_compounders":
		top := 15
		if t, ok := args["top"].(float64); ok && t > 0 {
			top = int(t)
		}
		minScore := 60.0
		if m, ok := args["min_score"].(float64); ok {
			minScore = m
		}
		showTraps := false
		if st, ok := args["show_traps"].(bool); ok {
			showTraps = st
		}
		compounds, err := engine.GetCompounderScreen(dataDir, minScore, !showTraps, "", top)
		if err != nil {
			return errorResult(err.Error())
		}
		return jsonResult(compounds)

	case "idx_analyze_dividend":
		ticker, _ := args["ticker"].(string)
		if ticker == "" {
			return errorResult("ticker argument is required")
		}
		dec, err := engine.AnalyzeDividend(dataDir, ticker)
		if err != nil {
			return errorResult(err.Error())
		}
		return jsonResult(dec)

	case "idx_screen_dividends":
		minYield := 4.0
		if my, ok := args["min_yield"].(float64); ok {
			minYield = my
		}
		limit := 15
		if l, ok := args["limit"].(float64); ok && l > 0 {
			limit = int(l)
		}
		results, err := engine.ScreenDividends(dataDir, minYield, limit)
		if err != nil {
			return errorResult(err.Error())
		}
		return jsonResult(results)

	case "idx_get_stealth_accumulation":
		top := 10
		if t, ok := args["top"].(float64); ok && t > 0 {
			top = int(t)
		}
		records, err := engine.ScanStealthAccumulation(dataDir, top)
		if err != nil {
			return errorResult(err.Error())
		}
		return jsonResult(records)

	case "idx_backtest_strategy":
		strategy, _ := args["strategy"].(string)
		holdingDays := 20
		if hd, ok := args["holding_days"].(float64); ok && hd > 0 {
			holdingDays = int(hd)
		}
		stopLoss := 0.0
		if sl, ok := args["stop_loss"].(float64); ok {
			stopLoss = sl
		}
		takeProfit := 0.0
		if tp, ok := args["take_profit"].(float64); ok {
			takeProfit = tp
		}
		summary, err := engine.RunStrategyBacktest(dataDir, strategy, holdingDays, 10, stopLoss, takeProfit)
		if err != nil {
			return errorResult(err.Error())
		}
		return jsonResult(summary)

	case "idx_get_peers":
		ticker, _ := args["ticker"].(string)
		if ticker == "" {
			return errorResult("ticker argument is required")
		}
		peers, err := engine.GetPeers(dataDir, ticker)
		if err != nil {
			return errorResult(err.Error())
		}
		return jsonResult(peers)

	default:
		return errorResult(fmt.Sprintf("unknown tool: %s", name))
	}
}

func jsonResult(v any) ToolResult {
	data, _ := json.MarshalIndent(v, "", "  ")
	return ToolResult{
		Content: []TextContent{
			{Type: "text", Text: string(data)},
		},
	}
}

func errorResult(msg string) ToolResult {
	return ToolResult{
		IsError: true,
		Content: []TextContent{
			{Type: "text", Text: msg},
		},
	}
}
