import yfinance as yf

# Define the ticker symbol for Bank Central Asia (Indonesia Stock Exchange)
ticker = yf.Ticker("BBCA.JK")

# Get institutional holders
institutional_holders = ticker.institutional_holders

# Get mutual fund holders
mutualfund_holders = ticker.mutualfund_holders

# Print the holders
print("Institutional Holders:")
print(institutional_holders)

print("\nMutual Fund Holders:")
print(mutualfund_holders)
