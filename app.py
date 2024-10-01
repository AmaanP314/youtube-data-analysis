from flask import Flask, request, render_template, redirect, url_for
from youtube_search import search_youtube

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form['query']
    sort_by = request.form['sort_by']
    max_results = int(request.form['max_results'])
    return redirect(url_for('results', query=query, sort_by=sort_by, max_results=max_results))

@app.route('/results')
def results():
    query = request.args.get('query')
    sort_by = request.args.get('sort_by')
    max_results = int(request.args.get('max_results'))
    data = search_youtube(query, sort_by=sort_by, max_results=max_results)
    
    if data == "quota_exceeded":
        return render_template('results.html', query=query, error="Today's Quota Exceeded🥲, Come back tomorrow!")
    
    if data is None:
        return render_template('results.html', query=query, error="No data found.")
    
    df, total_plot, comment_plot, engagement_rate_plot, composite_score_plot = data
    df.index = df.index + 1
    df_html = df.to_html(classes='table table-striped', index=True, escape=False)
    return render_template('results.html', query=query, table=df_html, total_plot=total_plot, comment_plot=comment_plot, engagement_rate_plot=engagement_rate_plot, composite_score_plot=composite_score_plot)

if __name__ == '__main__':
    app.run(debug=True)
