import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import requests
import time
import re

# Page configuration
st.set_page_config(
    page_title="Moving Average Crossover Scanner",
    page_icon="",
    layout="wide"
)

# Initialize session state for selected stock
if 'selected_stock_index' not in st.session_state:
    st.session_state.selected_stock_index = 0
    
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None
    
if 'last_scan_time' not in st.session_state:
    st.session_state.last_scan_time = None

# Title and description
st.title("Moving Average Crossover Scanner")
st.markdown("""
This app scans Nifty 500 stocks for moving average crossovers in real-time.
Select your preferred moving averages and scan for bullish/bearish crossovers.
""")

# Sidebar for parameters
st.sidebar.header("Scanner Parameters")

# Moving average selection
ma_short = st.sidebar.number_input("Short-term MA (days)", min_value=5, max_value=50, value=20, step=1)
ma_long = st.sidebar.number_input("Long-term MA (days)", min_value=20, max_value=200, value=50, step=1)

# Crossover type
crossover_type = st.sidebar.selectbox(
    "Crossover Type",
    ["Bullish (Short MA crosses above Long MA)", 
     "Bearish (Short MA crosses below Long MA)",
     "Both"]
)

# Number of stocks to scan
max_stocks = st.sidebar.slider("Number of stocks to scan", min_value=50, max_value=500, value=100, step=50)

# Chart period and interval selection
st.sidebar.markdown("---")
st.sidebar.subheader("Chart Settings")

chart_preset = st.sidebar.selectbox(
    "Chart Timeframe",
    ["Intraday (1min)", "Intraday (5min)", "Intraday (10min)", "Intraday (15min)", 
     "Intraday (30min)", "Intraday (1hr)", "Daily (1day)", "Weekly (1wk)", "Monthly (1mo)"],
    index=6  # Default to Daily
)

# Map preset to yfinance parameters
def get_chart_params(preset):
    """Map preset to yfinance interval and period"""
    params = {
        "Intraday (1min)": {"interval": "1m", "period": "7d", "max_days": 7},
        "Intraday (5min)": {"interval": "5m", "period": "1mo", "max_days": 30},
        "Intraday (10min)": {"interval": "10m", "period": "2mo", "max_days": 60},
        "Intraday (15min)": {"interval": "15m", "period": "2mo", "max_days": 60},
        "Intraday (30min)": {"interval": "30m", "period": "2mo", "max_days": 60},
        "Intraday (1hr)": {"interval": "1h", "period": "3mo", "max_days": 90},
        "Daily (1day)": {"interval": "1d", "period": "6mo", "max_days": None},
        "Weekly (1wk)": {"interval": "1wk", "period": "2y", "max_days": None},
        "Monthly (1mo)": {"interval": "1mo", "period": "5y", "max_days": None}
    }
    return params.get(preset, {"interval": "1d", "period": "6mo"})

# Get chart parameters
chart_params = get_chart_params(chart_preset)
chart_interval = chart_params["interval"]
chart_period = chart_params["period"]

st.sidebar.info(f"📊 Interval: {chart_interval} | Period: {chart_period}")

# Scan button
scan_button = st.sidebar.button("🔍 Scan for Crossovers", type="primary", use_container_width=True)

# Function to extract numeric value from string with ₹ symbol
def extract_numeric(value_str):
    """Extract numeric value from string like '₹1,234.56' or '1234.56'"""
    if isinstance(value_str, (int, float)):
        return float(value_str)
    # Remove ₹ symbol, commas, and % sign
    clean_str = re.sub(r'[₹,%]', '', str(value_str))
    try:
        return float(clean_str)
    except:
        return 0.0

# Improved function to get Nifty 500 stocks list from NSE
@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_nifty500_stocks():
    """Fetches the complete Nifty 500 stock list from NSE India."""
    url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/',
        'Origin': 'https://www.nseindia.com',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }

    stocks = []
    session = requests.Session()
    session.headers.update(headers)

    try:
        # Show progress in sidebar
        with st.sidebar.status("🔄 Connecting to NSE..."):
            # 1. First, visit the main page to get essential cookies
            main_page_url = "https://www.nseindia.com"
            session.get(main_page_url, timeout=10)
            time.sleep(3)  # Crucial: Wait for cookies to be set
            
            st.sidebar.info("📡 Fetching Nifty 500 stock list...")
            
            # 2. Now fetch the API data with the established session
            response = session.get(url, timeout=15)
            response.raise_for_status()  # Raise an exception for bad status codes

            data = response.json()

            if 'data' in data:
                # Iterate through the list, skipping the first item which is the index itself
                for item in data['data'][1:]:
                    if 'symbol' in item:
                        # Extract company name from meta if available
                        company_name = item['symbol']
                        industry = 'N/A'
                        
                        if 'meta' in item:
                            company_name = item['meta'].get('companyName', item['symbol'])
                            industry = item['meta'].get('industry', 'N/A')
                        
                        stocks.append({
                            'symbol': item['symbol'],
                            'company_name': company_name,
                            'industry': industry
                        })

            if stocks:
                st.sidebar.success(f"✅ Successfully fetched {len(stocks)} stocks from NSE!")
                return stocks
            else:
                st.sidebar.error("Received data from NSE but couldn't parse stocks.")
                return get_fallback_stocks()

    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"Network error fetching from NSE: {e}")
        return get_fallback_stocks()
    except Exception as e:
        st.sidebar.error(f"An unexpected error occurred: {e}")
        return get_fallback_stocks()

def get_fallback_stocks():
    """Return a curated list of major Nifty stocks as fallback"""
    st.sidebar.info("📋 Using curated stock list as fallback")
    
    return [
        {'symbol': 'RELIANCE', 'company_name': 'Reliance Industries Ltd.', 'industry': 'Oil & Gas'},
        {'symbol': 'TCS', 'company_name': 'Tata Consultancy Services Ltd.', 'industry': 'Information Technology'},
        {'symbol': 'HDFCBANK', 'company_name': 'HDFC Bank Ltd.', 'industry': 'Banking'},
        {'symbol': 'INFY', 'company_name': 'Infosys Ltd.', 'industry': 'Information Technology'},
        {'symbol': 'ICICIBANK', 'company_name': 'ICICI Bank Ltd.', 'industry': 'Banking'},
        {'symbol': 'HINDUNILVR', 'company_name': 'Hindustan Unilever Ltd.', 'industry': 'FMCG'},
        {'symbol': 'ITC', 'company_name': 'ITC Ltd.', 'industry': 'FMCG'},
        {'symbol': 'SBIN', 'company_name': 'State Bank of India', 'industry': 'Banking'},
        {'symbol': 'BHARTIARTL', 'company_name': 'Bharti Airtel Ltd.', 'industry': 'Telecommunications'},
        {'symbol': 'KOTAKBANK', 'company_name': 'Kotak Mahindra Bank Ltd.', 'industry': 'Banking'},
        {'symbol': 'BAJFINANCE', 'company_name': 'Bajaj Finance Ltd.', 'industry': 'Financial Services'},
        {'symbol': 'LT', 'company_name': 'Larsen & Toubro Ltd.', 'industry': 'Construction'},
        {'symbol': 'WIPRO', 'company_name': 'Wipro Ltd.', 'industry': 'Information Technology'},
        {'symbol': 'AXISBANK', 'company_name': 'Axis Bank Ltd.', 'industry': 'Banking'},
        {'symbol': 'TITAN', 'company_name': 'Titan Company Ltd.', 'industry': 'Consumer Goods'},
        {'symbol': 'MARUTI', 'company_name': 'Maruti Suzuki India Ltd.', 'industry': 'Automobile'},
        {'symbol': 'SUNPHARMA', 'company_name': 'Sun Pharmaceutical Industries Ltd.', 'industry': 'Pharmaceuticals'},
        {'symbol': 'ONGC', 'company_name': 'Oil & Natural Gas Corporation Ltd.', 'industry': 'Oil & Gas'},
        {'symbol': 'NTPC', 'company_name': 'NTPC Ltd.', 'industry': 'Power'},
        {'symbol': 'POWERGRID', 'company_name': 'Power Grid Corporation of India Ltd.', 'industry': 'Power'},
        {'symbol': 'ULTRACEMCO', 'company_name': 'UltraTech Cement Ltd.', 'industry': 'Cement'},
        {'symbol': 'HCLTECH', 'company_name': 'HCL Technologies Ltd.', 'industry': 'Information Technology'},
        {'symbol': 'TECHM', 'company_name': 'Tech Mahindra Ltd.', 'industry': 'Information Technology'},
        {'symbol': 'NESTLEIND', 'company_name': 'Nestlé India Ltd.', 'industry': 'FMCG'},
        {'symbol': 'BRITANNIA', 'company_name': 'Britannia Industries Ltd.', 'industry': 'FMCG'},
        {'symbol': 'ASIANPAINT', 'company_name': 'Asian Paints Ltd.', 'industry': 'Consumer Goods'},
        {'symbol': 'HDFC', 'company_name': 'Housing Development Finance Corporation Ltd.', 'industry': 'Financial Services'},
        {'symbol': 'DMART', 'company_name': 'Avenue Supermarts Ltd.', 'industry': 'Retail'},
        {'symbol': 'BAJAJFINSV', 'company_name': 'Bajaj Finserv Ltd.', 'industry': 'Financial Services'},
        {'symbol': 'ADANIPORTS', 'company_name': 'Adani Ports and Special Economic Zone Ltd.', 'industry': 'Infrastructure'},
        {'symbol': 'GRASIM', 'company_name': 'Grasim Industries Ltd.', 'industry': 'Cement'},
        {'symbol': 'JSWSTEEL', 'company_name': 'JSW Steel Ltd.', 'industry': 'Metals'},
        {'symbol': 'TATASTEEL', 'company_name': 'Tata Steel Ltd.', 'industry': 'Metals'},
        {'symbol': 'INDUSINDBK', 'company_name': 'IndusInd Bank Ltd.', 'industry': 'Banking'},
        {'symbol': 'DIVISLAB', 'company_name': 'Divi\'s Laboratories Ltd.', 'industry': 'Pharmaceuticals'},
        {'symbol': 'DRREDDY', 'company_name': 'Dr. Reddy\'s Laboratories Ltd.', 'industry': 'Pharmaceuticals'},
        {'symbol': 'CIPLA', 'company_name': 'Cipla Ltd.', 'industry': 'Pharmaceuticals'},
    ]

# Function to calculate moving averages and detect crossover
def detect_crossover(df, ma_short, ma_long):
    """Detect if there's a crossover in the latest data"""
    if len(df) < max(ma_short, ma_long) + 5:
        return None, None
    
    # Calculate moving averages
    df['MA_Short'] = df['Close'].rolling(window=ma_short).mean()
    df['MA_Long'] = df['Close'].rolling(window=ma_long).mean()
    
    # Get current and previous values
    current_short = df['MA_Short'].iloc[-1]
    current_long = df['MA_Long'].iloc[-1]
    prev_short = df['MA_Short'].iloc[-2] if len(df) > 2 else None
    prev_long = df['MA_Long'].iloc[-2] if len(df) > 2 else None
    
    # Check for crossover
    if pd.isna(current_short) or pd.isna(current_long) or prev_short is None or prev_long is None:
        return None, None
    
    # Bullish crossover: short MA crosses above long MA
    if prev_short <= prev_long and current_short > current_long:
        return 'Bullish', {
            'current_short': current_short,
            'current_long': current_long,
            'prev_short': prev_short,
            'prev_long': prev_long
        }
    
    # Bearish crossover: short MA crosses below long MA
    elif prev_short >= prev_long and current_short < current_long:
        return 'Bearish', {
            'current_short': current_short,
            'current_long': current_long,
            'prev_short': prev_short,
            'prev_long': prev_long
        }
    
    return None, None

# Function to fetch stock data with interval support
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_stock_data(symbol, interval="1d", period="6mo"):
    """Fetch stock data using yfinance with specified interval"""
    try:
        ticker = yf.Ticker(symbol + ".NS")  # NSE stocks
        
        # For 4hr interval, we need to fetch 1h data and resample
        if interval == "4h":
            df = ticker.history(period=period, interval="1h")
            if not df.empty and len(df) > 30:
                # Resample to 4-hour intervals
                df = df.resample('4H').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()
        else:
            df = ticker.history(period=period, interval=interval)
        
        if not df.empty and len(df) > 30:  # Ensure we have enough data
            return df
        return None
    except Exception as e:
        return None

# Function to create candlestick chart with improved legend placement
def create_candlestick_chart(df, symbol, ma_short, ma_long, interval):
    """Create a candlestick chart with moving averages"""
    try:
        # Create subplot with 2 rows (price and volume)
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3]
        )

        # Add candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Price',
                showlegend=True,
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350'
            ),
            row=1, col=1
        )

        # Add moving averages
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['MA_Short'],
                line=dict(color='orange', width=2),
                name=f'{ma_short}-period MA',
                mode='lines'
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['MA_Long'],
                line=dict(color='blue', width=2),
                name=f'{ma_long}-period MA',
                mode='lines'
            ),
            row=1, col=1
        )

        # Add volume bars with colors based on price movement
        colors = ['#ef5350' if row['Open'] > row['Close'] else '#26a69a' for index, row in df.iterrows()]
        
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['Volume'],
                name='Volume',
                marker_color=colors,
                opacity=0.7,
                showlegend=True
            ),
            row=2, col=1
        )

        # Update layout with improved legend placement
        interval_text = {
            "1m": "1 Minute", "5m": "5 Minutes", "10m": "10 Minutes", 
            "15m": "15 Minutes", "30m": "30 Minutes", "1h": "1 Hour",
            "1d": "Daily", "1wk": "Weekly", "1mo": "Monthly"
        }.get(interval, interval)
        
        fig.update_layout(
            title={
                'text': f'{symbol} - {interval_text} Chart with {ma_short}/{ma_long} MA',
                'y':0.98,
                'x':0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            yaxis_title='Price (₹)',
            template='plotly_dark',
            height=700,
            hovermode='x unified',
            xaxis_rangeslider_visible=False,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor='rgba(0,0,0,0.5)',
                bordercolor='rgba(255,255,255,0.3)',
                borderwidth=1
            ),
            margin=dict(l=50, r=50, t=80, b=50)
        )

        # Update y-axis labels
        fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

        return fig
    
    except Exception as e:
        st.error(f"Error creating chart: {str(e)}")
        return None

# Main scanning function
def scan_stocks(stocks, ma_short, ma_long, crossover_type, max_stocks):
    """Scan stocks for moving average crossovers"""
    results = []
    bullish_count = 0
    bearish_count = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Ensure we don't try to scan more than available
    scan_count = min(max_stocks, len(stocks))
    
    for i, stock in enumerate(stocks[:scan_count]):
        status_text.text(f"Scanning {i+1}/{scan_count}: {stock['symbol']}")
        progress_bar.progress((i + 1) / scan_count)
        
        # Fetch data with daily interval for scanning (to be consistent)
        df = fetch_stock_data(stock['symbol'], interval="1d", period="6mo")
        if df is not None:
            crossover, values = detect_crossover(df, ma_short, ma_long)
            
            if crossover:
                if crossover_type == "Both" or \
                   (crossover_type == "Bullish (Short MA crosses above Long MA)" and crossover == 'Bullish') or \
                   (crossover_type == "Bearish (Short MA crosses below Long MA)" and crossover == 'Bearish'):
                    
                    # Get current price
                    current_price = df['Close'].iloc[-1]
                    
                    # Calculate price change
                    price_change = ((current_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100 if len(df) > 1 else 0
                    
                    # Calculate volume
                    avg_volume = df['Volume'].tail(20).mean()
                    current_volume = df['Volume'].iloc[-1]
                    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
                    
                    # Store numeric values for sorting and styling
                    results.append({
                        'Symbol': stock['symbol'],
                        'Company': stock['company_name'],
                        'Industry': stock['industry'],
                        'Crossover Type': crossover,
                        'Current Price': current_price,
                        'Price Change %': price_change,
                        'Short MA': values['current_short'],
                        'Long MA': values['current_long'],
                        'Difference %': ((values['current_short'] - values['current_long']) / values['current_long'] * 100),
                        'Volume Ratio': volume_ratio,
                        'Signal Strength': 'Strong' if abs(price_change) > 2 and volume_ratio > 1.5 else 'Moderate'
                    })
                    
                    if crossover == 'Bullish':
                        bullish_count += 1
                    else:
                        bearish_count += 1
        
        time.sleep(0.2)  # Rate limiting to avoid API bans
    
    status_text.text(f"Scan completed! Found {len(results)} crossovers out of {scan_count} stocks scanned")
    return results, bullish_count, bearish_count, scan_count

# Function to format DataFrame for display
def format_display_df(df):
    """Format the DataFrame for display with proper styling"""
    display_df = df.copy()
    
    # Format numeric columns
    display_df['Current Price'] = display_df['Current Price'].apply(lambda x: f"₹{x:,.2f}")
    display_df['Price Change %'] = display_df['Price Change %'].apply(lambda x: f"{x:+.2f}%")
    display_df['Short MA'] = display_df['Short MA'].apply(lambda x: f"₹{x:,.2f}")
    display_df['Long MA'] = display_df['Long MA'].apply(lambda x: f"₹{x:,.2f}")
    display_df['Difference %'] = display_df['Difference %'].apply(lambda x: f"{x:+.2f}%")
    display_df['Volume Ratio'] = display_df['Volume Ratio'].apply(lambda x: f"{x:.2f}x")
    
    return display_df

# Main app logic
if scan_button:
    with st.spinner("Fetching Nifty 500 stocks list..."):
        stocks = get_nifty500_stocks()
        
    if stocks:
        st.success(f"✅ Found {len(stocks)} stocks in the Nifty 500 list")
        
        # Perform scan
        results, bullish_count, bearish_count, scanned_count = scan_stocks(
            stocks, ma_short, ma_long, crossover_type, max_stocks
        )
        
        # Store results in session state
        st.session_state.scan_results = results
        st.session_state.last_scan_time = datetime.now()
        
        # Display summary statistics
        st.header("📊 Scan Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Stocks in Database", len(stocks))
        with col2:
            st.metric("Stocks Scanned", scanned_count)
        with col3:
            st.metric("Total Crossovers", len(results))
        with col4:
            st.metric("Bullish/Bearish", f"{bullish_count}/{bearish_count}")
        
        # Display results
        if results:
            st.header(f"🎯 Stocks with {ma_short}/{ma_long} MA Crossovers")
            
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Sort by difference percentage (strongest crossovers first)
            results_df = results_df.sort_values('Difference %', ascending=False)
            
            # Create display version with formatted strings
            display_df = format_display_df(results_df)
            
            # Apply styling using Streamlit's built-in coloring
            def color_crossover(val):
                if val == 'Bullish':
                    return 'background-color: #90EE90'
                elif val == 'Bearish':
                    return 'background-color: #FFB6C1'
                return ''
            
            # Apply styling to the display DataFrame
            styled_df = display_df.style.map(color_crossover, subset=['Crossover Type'])
            
            # Display the styled dataframe
            st.dataframe(styled_df, use_container_width=True, height=400)
            
            # Download button for raw data
            csv = results_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv,
                file_name=f"ma_crossover_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            # Store results DataFrame in session state for chart view
            st.session_state.results_df = results_df
            
        else:
            st.info(f"No {crossover_type.lower()} crossovers found in the scanned stocks.")
            st.session_state.results_df = None
    else:
        st.error("Failed to fetch stocks list. Please try again later.")

# Detailed Chart View - Always visible if results exist
if st.session_state.scan_results and len(st.session_state.scan_results) > 0:
    st.header("📈 Detailed Chart View")
    
    # Create a list of options with company names
    results_df = pd.DataFrame(st.session_state.scan_results)
    stock_options = [f"{row['Symbol']} - {row['Company']}" for _, row in results_df.iterrows()]
    
    # Use session state to maintain selected stock
    selected_index = st.session_state.get('selected_stock_index', 0)
    
    # Create selectbox with key to maintain state
    selected_option = st.selectbox(
        "Select a stock to view detailed chart", 
        options=stock_options,
        index=selected_index,
        key='stock_selector'
    )
    
    # Update session state with selected index
    st.session_state.selected_stock_index = stock_options.index(selected_option)
    
    if selected_option:
        selected_symbol = selected_option.split(" - ")[0]
        
        # Find the selected stock data
        selected_stock_data = results_df[results_df['Symbol'] == selected_symbol].iloc[0]
        
        # Display stock info in columns
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.info(f"**Crossover:** {selected_stock_data['Crossover Type']}")
        with col2:
            st.info(f"**Price:** ₹{selected_stock_data['Current Price']:,.2f}")
        with col3:
            st.info(f"**Change:** {selected_stock_data['Price Change %']:+.2f}%")
        with col4:
            st.info(f"**Signal:** {selected_stock_data['Signal Strength']}")
        
        # Fetch data for chart with selected interval
        with st.spinner(f"Loading {chart_interval} chart data for {selected_symbol}..."):
            df = fetch_stock_data(selected_symbol, interval=chart_interval, period=chart_period)
            
        if df is not None and len(df) > 30:
            # Calculate MAs for the chart
            df['MA_Short'] = df['Close'].rolling(window=ma_short).mean()
            df['MA_Long'] = df['Close'].rolling(window=ma_long).mean()
            
            # Create and display chart
            fig = create_candlestick_chart(df, selected_symbol, ma_short, ma_long, chart_interval)
            
            if fig:
                st.plotly_chart(fig, use_container_width=True)
                
                # Add some statistics
                st.subheader("📊 Key Statistics")
                col1, col2, col3 = st.columns(3)
                
                # Calculate statistics based on available data
                with col1:
                    st.metric("Period High", f"₹{df['High'].max():,.2f}")
                with col2:
                    st.metric("Period Low", f"₹{df['Low'].min():,.2f}")
                with col3:
                    st.metric("Avg Volume", f"{df['Volume'].mean():,.0f}")
                
                # Show data info
                st.caption(f"📅 Data from {df.index[0].strftime('%Y-%m-%d %H:%M')} to {df.index[-1].strftime('%Y-%m-%d %H:%M')} | {len(df)} candles")
            else:
                st.error("Could not create chart. Please try another stock or timeframe.")
        else:
            st.warning(f"Insufficient data available for {selected_symbol} with {chart_interval} interval. Try a different timeframe.")
elif st.session_state.scan_results is not None and len(st.session_state.scan_results) == 0:
    st.info("No crossovers found. Run a scan to see results.")

# Auto-refresh option
st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("Auto-refresh every 5 minutes")
if auto_refresh:
    st.sidebar.info("Auto-refresh is enabled. Page will refresh every 5 minutes.")
    time.sleep(300)  # Wait 5 minutes
    st.rerun()

# Footer
st.markdown("---")
st.markdown(f"""
<div style='text-align: center'>
    <p>⚠️ <strong>Disclaimer:</strong> This is for informational purposes only. 
    Always do your own research before making investment decisions.</p>
    <p>Data source: NSE India & Yahoo Finance | Last updated: {st.session_state.last_scan_time.strftime("%Y-%m-%d %H:%M:%S") if st.session_state.last_scan_time else 'Never'}</p>
    <p>📊 Scanned {max_stocks if 'max_stocks' in locals() else 'N/A'} stocks with {ma_short}/{ma_long} MA crossover | Chart: {chart_preset}</p>
</div>
""", unsafe_allow_html=True)