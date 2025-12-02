# **Crypto Volume Analysis Toolkit**

Lightweight and simple toolkit that helps you track high-volume crypto tokens in the last 24 hours and run cross-market analysis using spot + futures data and generate reports in a pdf.

The generated report is a valuable asset to cryto analysts and trades alike.

# **Demo**

![One Page Screenshor - Excludes Remaining Spot Tokens](https://github.com/traderabba/Crypto-Volume-Analysis-Toolkit/blob/images/demo.jpg)

# **Features**

- Easy to use
- Fast, lightweight, and reliable
- Execute the task in around 45 secs
- Works on any device
- No complex setup
- Automatic Spot Volume Tracking
- Advanced Futures + Spot Analysis
- Automatic clean HTML report generation
- Automatic PDF export
- Cleans up after finishing
- Multi-source verification reduces errors
- Useful for daily analysis routines
- Explainer for Open Interest Signal Score (OISS)

# **Installation & Setup**

Before running the toolkit, you need to install these four libraries in your python or Pydroid3 environment:


`pip install requests pandas beautifulsoup4 pypdf`

## API keys Setup

Set these in your environment:

- HTML2PDF_API_KEY

- CMC_API_KEY

- LIVECOINWATCH_API_KEY

- COINRANKINGS_API_KEY

## CoinAlyze VRMR Setup

To use the tool efficiently, you need specific futures data from CoinAlyze:

- Go to https://CoinAlyze.net and sign up.

- Navigate to **Custom Metrics** and tap on **Create Custom Metrics**.

- Enter **VTMR** in the Name and Short Name fields, then paste the **VTMR code** in the Expression field 'n save & close.

`((vol_1d[0] / mc_1d[0]) * 10) / 10 * (vol_1d[0] / mc_1d[0] >= 0.5)`

- Go to **Columns**, deselect all, and select **Market Capitalization**, **Volume 24H**, **Open Interest Change % 24H** and **VTMR**, then click **Apply**.

- Bookmark the page and save it as VTMR.

- Go to Chrome menu → Share → Print, and save it as it is without changing the file name in the Download folder.

### Why do This?

Because before you run the toolkit, you need fresh futures data from CoinAlyze. So basically, you only need to launch Chrome  → type VTMR and open it  → print the page into the Download folder. 

After you run the toolkit, it will take care of cleaning your download folder and leaving only the most valuable reports there. 

# Disclaimer

This toolkit is for research and educational purposes only. It does not, in any way, provide financial advice, trading signals, or investment recommendations.

# Contribute

MIT licensed — use, modify, or build freely.  

Contribute via issues, PRs, or feature suggestions.  

All contributions stay MIT.

# Changelog

- v1.0: full version created and uploaded   on Nov. 30,2025.
- v2.0: Integrated IOSS and explainer added on Dec. 02,2025.
- Removed v1.0 from directory and leave v2.0 on Dec. 02,2025.
