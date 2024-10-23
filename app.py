import streamlit as st
import pandas as pd
from crawler import WebCrawler
import plotly.express as px
from database import Session
from models import CrawlResult
st.set_page_config(layout="wide")
def main():
    st.title("Web Crawler App")
    
    # Input fields
    start_url = st.text_input("Enter the starting URL:", "https://toscrape.com/")
    max_depth = st.slider("Maximum crawl depth:", 1, 5, 2)
    requests_per_second = st.slider("Requests per second:", 0.1, 10.0, 2.0, 0.1,
                                  help="Rate limit for crawler requests. Lower values are gentler on the target server.")
    domains = st.text_input("Allowed domains (comma-separated, leave empty for all):", "")
    blacklist = st.text_input("Blacklisted extensions (comma-separated):", ".jpg,.css,.js,.png")

    if st.button("Start Crawling"):
        # Process inputs
        domains = [d.strip() for d in domains.split(",")] if domains else []
        blacklist = [b.strip() for b in blacklist.split(",")]

        # Initialize and run the crawler with rate limiting
        crawler = WebCrawler(
            max_depth=max_depth, 
            domains=domains, 
            blacklist=blacklist,
            requests_per_second=requests_per_second
        )
        crawler.crawl(start_url)

        # Read results from database
        db_session = Session()
        results = db_session.query(CrawlResult).all()

        # Convert database results to DataFrame
        df = pd.DataFrame([
            {
                "URL": result.url,
                "Parent URL": result.parent_url,
                "Status Code": result.status_code,
                "Content Size": result.content_size,
                "Title": result.title,
                "Statistics": str(result.statistics)  # Combined statistics into one column
            } for result in results
        ])

        # Display results
        st.subheader("Crawl Results")
        
        # Display the DataFrame
        st.dataframe(df)

        # Create and display charts
        st.subheader("Crawl Statistics")

        # Status Code Distribution
        status_codes = [result.status_code for result in results if result.status_code]
        fig_status = px.histogram(x=status_codes, labels={'x': 'Status Code', 'y': 'Count'}, title="Status Code Distribution")
        # Force x-axis to treat values as strings/categories
        fig_status.update_xaxes(type='category')
        st.plotly_chart(fig_status)

        # Content Size Distribution
        content_sizes = [result.content_size for result in results]
        fig_size = px.histogram(x=content_sizes, labels={'x': 'Content Size (bytes)', 'y': 'Count'}, title="Content Size Distribution")
        st.plotly_chart(fig_size)

        # Domain Statistics
        domain_stats = {}
        for result in results:
            for domain, count in result.statistics.get('domain_stats', {}).items():
                domain_stats[domain] = domain_stats.get(domain, 0) + count
        
        fig_domains = px.bar(x=list(domain_stats.keys()), y=list(domain_stats.values()), labels={'x': 'Domain', 'y': 'Count'}, title="Domain Statistics")
        st.plotly_chart(fig_domains)

        db_session.close()

if __name__ == "__main__":
    main()
