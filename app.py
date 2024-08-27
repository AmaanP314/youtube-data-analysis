from flask import Flask, request, render_template, redirect, url_for
from youtube_search import search_youtube, viz_combined, plot_to_base64, strip_emojis
from flask_mysqldb import MySQL
import pandas as pd

app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'GTA6FREE1'
app.config['MYSQL_DB'] = 'youtube_data'
app.config['MYSQL_DATABASE_CHARSET'] = 'utf8mb4'

mysql = MySQL(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form['query']
    sort_by = request.form['sort_by']
    max_results = int(request.form['max_results'])
    cur = mysql.connection.cursor()
    cur.execute("SELECT query FROM search WHERE query = %s", (query,))
    search_exists = cur.fetchone()
    if search_exists:
        cur.execute("UPDATE search SET last_searched = NOW() WHERE query = %s", (query,))
        mysql.connection.commit()
    cur.close()
    if search_exists:
        return redirect(url_for('results', query=query, sort_by=sort_by, max_results=max_results, use_db=True))
    else:
        return redirect(url_for('results', query=query, sort_by=sort_by, max_results=max_results, use_db=False))

@app.route('/results')
def results():
    query = request.args.get('query')
    sort_by = request.args.get('sort_by')
    max_results = int(request.args.get('max_results'))
    use_db = request.args.get('use_db')
    
    if use_db == 'True':
        cur = mysql.connection.cursor()
        cur.execute('''SELECT results.* FROM search
                       JOIN results ON search.id = results.sId
                       WHERE search.query = %s''', (query,))
        videos_data = cur.fetchall()
        cur.close()
        
        if not videos_data:
            return render_template('results.html', query=query, error="No data found in database.")
        
        df = pd.DataFrame(videos_data, columns=['rId', 'title', 'channel_name', 'subscribers', 'views', 'likes', 'likes(%)', 'duration_minutes', 'upload_date', 'comments', 'video_link', 'sId'])
        df.drop(columns=['rId', 'sId'], inplace=True)
        
        total_plot = plot_to_base64(viz_combined, df, plot_type='total')
        percent_plot = plot_to_base64(viz_combined, df, plot_type='percent')
        engagement_rate_plot = plot_to_base64(viz_combined, df, plot_type='engagement_rate')
        composite_score_plot = plot_to_base64(viz_combined, df, plot_type='composite_score')
        df.index = df.index + 1
        df_html = df.to_html(classes='table table-striped', index=True, escape=False)
    
    else:
        data = search_youtube(query, sort_by=sort_by, max_results=max_results)
        if data is None:
            return render_template('results.html', query=query, error="No data found.")
        
        df, total_plot, percent_plot, engagement_rate_plot, composite_score_plot = data
        df.index = df.index + 1
        df_html = df.to_html(classes='table table-striped', index=True, escape=False)
        
        cur = mysql.connection.cursor()
        cur.execute('''INSERT INTO search(query, first_searched, last_searched)
                       VALUES (%s, NOW(), NOW())''', (query,))
        search_id = cur.lastrowid
        
        for index, row in df.iterrows():
            title = strip_emojis(row['title'])
            channel_name = strip_emojis(row['channel_name'])
            try:
                cur.execute('''INSERT INTO results(title, channel_name, subscribers, views, likes, likes_percent, duration_minutes, upload_date, comments, video_link, sId)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                               (title, channel_name, row['subscribers'], row['views'], row['likes'], row['likes(%)'], row['duration_minutes'], row['upload_date'], row['comments'], row['video_link'], search_id))
            except Exception as e:
                print(f"Error inserting row: {row}\nError: {e}")
        mysql.connection.commit()
        cur.close()
    
    return render_template('results.html', query=query, table=df_html, total_plot=total_plot, percent_plot=percent_plot, engagement_rate_plot=engagement_rate_plot, composite_score_plot=composite_score_plot)

if __name__ == '__main__':
    app.run(debug=True)
