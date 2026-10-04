package models

// Company fundamental profile.
type Company struct {
	Code            string   `json:"code"`
	Name            string   `json:"name"`
	Sector          string   `json:"sector"`
	SubSector       string   `json:"sub_sector"`
	Industry        string   `json:"industry"`
	SubIndustry     string   `json:"sub_industry"`
	ROE             float64  `json:"roe"`
	ROA             float64  `json:"roa"`
	NPM             float64  `json:"npm"`
	DERatio         float64  `json:"de_ratio"`
	PER             float64  `json:"per"`
	PriceBV         float64  `json:"price_bv"`
	Assets          float64  `json:"assets"`
	Liabilities     float64  `json:"liabilities"`
	Equity          float64  `json:"equity"`
	Sales           float64  `json:"sales"`
	ProfitPeriod    float64  `json:"profit_period"`
	EPS             float64  `json:"eps"`
	BookValue       float64  `json:"book_value"`
	FSDate          string   `json:"fs_date"`
	EstimatedMCap   float64  `json:"estimated_mcap"`
	Score           any      `json:"score"`
	CompounderScore float64  `json:"compounder_score,omitempty"`
	IsValueTrap     bool     `json:"is_value_trap,omitempty"`
	DCAVerdict      string   `json:"dca_verdict,omitempty"`
	ValuationStatus string   `json:"valuation_status,omitempty"`
	ForensicFlags   []string `json:"forensic_flags,omitempty"`
	BoardMembers    any      `json:"board_members,omitempty"`
	Shareholders    any      `json:"shareholders,omitempty"`
	Subsidiaries    any      `json:"subsidiaries,omitempty"`
}

// NetworkAlphaData wraps data/network_alpha_data.json.
type NetworkAlphaData struct {
	Companies     []Company `json:"companies"`
	SuperInsiders any       `json:"super_insiders"`
	Conglomerates any       `json:"conglomerates"`
}

// ParquetStockRow maps directly to parquet columns in stock_summary.
type ParquetStockRow struct {
	Date                string  `parquet:"Date"`
	StockCode           string  `parquet:"StockCode"`
	StockName           string  `parquet:"StockName"`
	Previous            float64 `parquet:"Previous"`
	OpenPrice           float64 `parquet:"OpenPrice"`
	High                float64 `parquet:"High"`
	Low                 float64 `parquet:"Low"`
	Close               float64 `parquet:"Close"`
	Change              float64 `parquet:"Change"`
	Volume              float64 `parquet:"Volume"`
	Value               float64 `parquet:"Value"`
	Frequency           float64 `parquet:"Frequency"`
	ForeignSell         float64 `parquet:"ForeignSell"`
	ForeignBuy          float64 `parquet:"ForeignBuy"`
	NonRegularVolume    float64 `parquet:"NonRegularVolume"`
	NonRegularValue     float64 `parquet:"NonRegularValue"`
	NonRegularFrequency float64 `parquet:"NonRegularFrequency"`
}

// StockRecord represents standardized JSON output for charts and technical indicators.
type StockRecord struct {
	Date                string   `json:"Date"`
	Time                string   `json:"time"`
	StockCode           string   `json:"StockCode"`
	StockName           string   `json:"StockName,omitempty"`
	Open                float64  `json:"open"`
	High                float64  `json:"high"`
	Low                 float64  `json:"low"`
	Close               float64  `json:"close"`
	Volume              float64  `json:"volume"`
	Value               float64  `json:"Value"`
	Frequency           float64  `json:"Frequency"`
	NetForeignFlow      float64  `json:"NetForeignFlow"`
	ForeignBuy          float64  `json:"ForeignBuy"`
	ForeignSell         float64  `json:"ForeignSell"`
	NonRegularVolume    float64  `json:"NonRegularVolume,omitempty"`
	NonRegularValue     float64  `json:"NonRegularValue,omitempty"`
	RSI14               *float64 `json:"RSI14,omitempty"`
	EMA20               *float64 `json:"EMA20,omitempty"`
	EMA50               *float64 `json:"EMA50,omitempty"`
	EMA200              *float64 `json:"EMA200,omitempty"`
	BBUpper             *float64 `json:"BB_Upper,omitempty"`
	BBMid               *float64 `json:"BB_Mid,omitempty"`
	BBLower             *float64 `json:"BB_Lower,omitempty"`
	ATR14               *float64 `json:"ATR14,omitempty"`
}

// BrokerSummaryRecord represents broker transactions.
type BrokerSummaryRecord struct {
	Date       string  `json:"Date" parquet:"Date"`
	BrokerCode string  `json:"BrokerCode" parquet:"BrokerCode"`
	BrokerName string  `json:"BrokerName" parquet:"BrokerName"`
	BuyVolume  float64 `json:"BuyVolume" parquet:"BuyVolume"`
	BuyValue   float64 `json:"BuyValue" parquet:"BuyValue"`
	SellVolume float64 `json:"SellVolume" parquet:"SellVolume"`
	SellValue  float64 `json:"SellValue" parquet:"SellValue"`
}
