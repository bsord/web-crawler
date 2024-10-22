import streamlit as st
import pandas as pd
from crawler import WebCrawler
import plotly.express as px

def main():
    st.title("Web Crawler App")

    # Input fields
    start_url = st.text_input("Enter the starting URL:", "https://toscrape.com/")
    max_depth = st.slider("Maximum crawl depth:", 1, 5, 2)
    domains = st.text_input("Allowed domains (comma-separated, leave empty for all):", "")
    blacklist = st.text_input("Blacklisted extensions (comma-separated):", ".jpg,.css,.js,.png")

    if st.button("Start Crawling"):
        # Process inputs
        domains = [d.strip() for d in domains.split(",")] if domains else []
        blacklist = [b.strip() for b in blacklist.split(",")]

        # Initialize and run the crawler
        crawler = WebCrawler(max_depth=max_depth, domains=domains, blacklist=blacklist)
        results = crawler.crawl(start_url)

        # Display results
        st.subheader("Crawl Results")
        
        # Convert results to a DataFrame
        df = pd.DataFrame([
            {
                "URL": url,
                "Status Code": data['status_code'],
                "Content Size": data['content_size'],
                "Title": data['title'],
                "Total URLs Crawled": data['statistics']['total_urls_crawled'],
                "Total Errors": data['statistics']['total_errors']
            } for url, data in results
        ])

        # Display the DataFrame
        st.dataframe(df)

        # Create and display charts
        st.subheader("Crawl Statistics")

        # Status Code Distribution
        status_codes = [data['status_code'] for _, data in results if data['status_code']]
        fig_status = px.histogram(x=status_codes, labels={'x': 'Status Code', 'y': 'Count'}, title="Status Code Distribution")
        st.plotly_chart(fig_status)

        # Content Size Distribution
        content_sizes = [data['content_size'] for _, data in results]
        fig_size = px.histogram(x=content_sizes, labels={'x': 'Content Size (bytes)', 'y': 'Count'}, title="Content Size Distribution")
        st.plotly_chart(fig_size)

        # Domain Statistics
        domain_stats = {}
        for _, data in results:
            for domain, count in data['statistics']['domain_stats'].items():
                domain_stats[domain] = domain_stats.get(domain, 0) + count
        
        fig_domains = px.bar(x=list(domain_stats.keys()), y=list(domain_stats.values()), labels={'x': 'Domain', 'y': 'Count'}, title="Domain Statistics")
        st.plotly_chart(fig_domains)

if __name__ == "__main__":
    main()
