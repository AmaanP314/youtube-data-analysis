from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from transformers import pipeline
import isodate
import matplotlib
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import PercentFormatter, FuncFormatter
import warnings
import io
import os
import base64
import re

matplotlib.use('Agg')
warnings.filterwarnings("ignore", module="matplotlib")
sns.set()
api_key = 'AIzaSyDtqLe7rRVVuYq3HsjbLOov-3mf_ZI2Mlg'
# api_key = os.getenv('YOUTUBE_API_KEY')

youtube = build('youtube', 'v3', developerKey = api_key)

sentiment_model = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment")
label_map = {"LABEL_0": "Negative", "LABEL_1": "Neutral", "LABEL_2": "Positive"}

def get_video_details(video_id):
    try:
        video_request = youtube.videos().list(
            part='snippet,contentDetails,statistics',
            id=video_id
        )
        video_response = video_request.execute()

        if not video_response['items']:
            return None

        video = video_response['items'][0]
        snippet = video['snippet']
        statistics = video['statistics']
        content_details = video['contentDetails']

        duration_seconds = (isodate.parse_duration(content_details['duration']).total_seconds())
        duration_minutes = duration_seconds // 60

        if duration_seconds <= 60:
            return None

        channel_id = snippet['channelId']
        channel_request = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id
        )
        channel_response = channel_request.execute()
        if not channel_response['items']:
            return None
        
        channel = channel_response['items'][0]
        channel_statistics = channel['statistics']

        video_link = f"https://www.youtube.com/watch?v={video_id}"

        video_details = {
            'title': snippet['title'],
            'views': int(statistics.get('viewCount', 0)),
            'likes': int(statistics.get('likeCount', 0)),
            'comments': int(statistics.get('commentCount', 0)),
            'upload_date': snippet['publishedAt'],
            'duration_minutes': int(duration_minutes),
            'channel_name': snippet['channelTitle'],
            'subscribers': int(channel_statistics.get('subscriberCount', 0)),
            'video_link': video_link 
        }

        return video_details
    
    except Exception as e:
        print(f"An error occurred while fetching video details: {e}")
        return None

def get_comments(video_id, order='relevance', maxResults=10):
    positive, neutral, negative = (0,0,0)
    comment_req = youtube.commentThreads().list(
        part='snippet',
        videoId=video_id,
        textFormat='plainText',
        order=order,
        maxResults=maxResults
    )
    comments_response = comment_req.execute()

    for comment_item in comments_response['items']:
        try:
            comment = comment_item['snippet']['topLevelComment']['snippet']['textDisplay']
            result = sentiment_model(comment)
            sentiment = label_map[result[0]['label']]
            if sentiment == 'Positive':
                positive += 1
            elif sentiment == 'Negative':
                negative += 1
            else:
                neutral += 1
            # print(f"\t Comment: {comment}\nSentiment: {sentiment} (Confidence Score: {result[0]['score']:.4f})\n")
        except Exception as e:
            # print(f"Error processing comment: {e}")
            pass
    return {'Positive': positive, 'Negative': negative, 'Neutral': neutral}
    
def get_data(search, sort_by='relevance', max_results=5):
    videos_data = []
    comments_data = []
    try:
        req = youtube.search().list(
            q=search,
            part='snippet',
            type='video',
            order=sort_by,
            maxResults=max_results
        )
        response = req.execute()
        
        for item in response['items']:
            video_id = item['id']['videoId']
            video_data = get_video_details(video_id)
            if video_data is not None:
                comment_data = get_comments(video_id, maxResults=10)
                videos_data.append(video_data)
                comments_data.append(comment_data)
    
    except HttpError as e:
        error_code = e.resp.status
        if error_code == 403:
            # print("YouTube API quota has been exceeded.")
            return "quota_exceeded"
        else:
            # print(f"An HTTP error occurred: {e}")
            return None
    
    except Exception as e:
        # print(f"An error occurred: {e}")
        return None
    
    return videos_data, comments_data

def viz_combined(df, plot_type='total'):
    if len(df) <= 20:
        fig, ax = plt.subplots(figsize=(12, 8))
        bottom_margin = 0.25 + 0.07 * (len(df) // 5)
    elif len(df) <= 40:
        fig, ax = plt.subplots(figsize=(14, 10))
        bottom_margin = 0.17 + 0.05 * (len(df) // 5)
    else:
        fig, ax = plt.subplots(figsize=(18, 14))
        bottom_margin = 0.1 + 0.05 * (len(df) // 5)
        
    colors = ['#03045e','#023e8a','#0077b6','#0096c7','#00b4d8','#48cae4','#90e0ef','#ade8f4']
    sns.set_style('white')

    if plot_type == 'total' or plot_type == 'percent':
        ax.bar(df.index + 1, df['views'], color=colors)

        if plot_type == 'total':
            ax2 = ax.twinx()
            ax2.plot(df.index + 1, df['likes'], color='crimson', marker='D')
            ax2.set_ylabel('Likes', fontsize=13, fontweight='bold')
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x):,}'))
        elif plot_type == 'percent':
            ax2 = ax.twinx()
            ax2.set_ylim(0, 1)
            ax2.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
            ax2.plot(df.index + 1, df['likes(%)'] / 100, color='crimson', marker='D')
            ax2.set_ylabel('Likes (%)', fontsize=13, fontweight='bold')
        else:
            raise ValueError("Invalid plot_type. Use 'total' or 'percent'.")

        ax.set_ylabel('Views', fontsize=13, fontweight='bold')
        plt.title('Views and Likes Graph' if plot_type == 'total' else 'Views and Likes Percentage by Views', fontsize=16, fontweight='bold')

    elif plot_type == 'engagement_rate':
        df['engagement_rate'] = (df['likes'] + df['comments']) / df['views']
        ax.bar(df.index + 1, df['engagement_rate'], color=colors)
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
        ax.set_ylim(0, df['engagement_rate'].max() * 1.1)
        ax.set_ylabel('Engagement Rate (%)', fontsize=13, fontweight='bold')
        plt.title('Engagement Rate by Video', fontsize=16, fontweight='bold')

    elif plot_type == 'composite_score':
        df['engagement_rate'] = (df['likes'] + df['comments']) / df['views']
        df['composite_score'] = (df['views'] * 0.4) + (df['likes'] * 0.2) + (df['comments'] * 0.2) + (df['engagement_rate'] * 0.1) + (df['subscribers'] * 0.1)
        ax.bar(df.index + 1, df['composite_score'], color=colors)
        ax.set_ylabel('Composite Score', fontsize=13, fontweight='bold')
        plt.title('Composite Score by Video', fontsize=16, fontweight='bold')

    else:
        raise ValueError("Invalid plot_type. Use 'total', 'percent', 'engagement_rate', or 'composite_score'.")

    while len(colors) < len(df):
        colors.extend(colors)

    handles = [plt.Line2D([0], [0], color=c, marker='o', label=f"{num}: {name}", markersize=10, linestyle='None') 
               for num, name, c in zip(df.index + 1, df['title'], colors)]

    legend = ax.legend(handles=handles, title='Title Mapping', loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2)
    plt.setp(legend.get_title(), fontsize=13, fontweight='bold')

    ax.set_xlabel('Title Number', fontsize=13, fontweight='bold')
    ax.set_xticks(range(1, len(df) + 1))
    ax.set_xticklabels(range(1, len(df) + 1))
    if plot_type == 'total' or plot_type == 'percent' or plot_type == 'composite_score':
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x):,}'))
    else:
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.2%}'))

    plt.rcParams['font.family'] = 'DejaVu Sans'
    if len(df) > 40:
        plt.tight_layout()

    fig.subplots_adjust(bottom=bottom_margin)
    
    for text in legend.get_texts():
        text.set_fontsize(10)
    legend.get_frame().set_linewidth(0.5)

    plt.show()

def sentiment_viz(df):
    ax = df.plot(kind='bar', stacked=True, figsize=(12, 6), color=['#28a745', '#dc3545', '#bfbfbf'])
    plt.title('Sentiment Analysis for Multiple Videos')
    plt.xlabel('Video Index')
    plt.ylabel('Number of Comments')
    plt.xticks(ticks=range(len(df)), labels=[i + 1 for i in range(len(df))], rotation=0)
    plt.legend(['Positive', 'Negative', 'Neutral'])

def search_youtube(search_query, sort_by='relevance', max_results=10):
    videos_data, comments_data = get_data(search_query, sort_by, max_results)
    
    if videos_data == "quota_exceeded":
        return "quota_exceeded"
    
    if not videos_data:
        return None

    df = pd.DataFrame(videos_data)
    df_com = pd.DataFrame(comments_data)
    try:
        df['upload_date'] = pd.to_datetime(df['upload_date'].str.split('T').str[0])
        df['likes(%)'] = (df['likes'] / df['views']) * 100
        df = df[['title', 'channel_name', 'subscribers', 'views', 'likes', 'likes(%)', 'duration_minutes', 'upload_date', 'comments', 'video_link']]
        
        total_plot = plot_to_base64(viz_combined, df, plot_type='total')
        engagement_rate_plot = plot_to_base64(viz_combined, df, plot_type='engagement_rate')
        composite_score_plot = plot_to_base64(viz_combined, df, plot_type='composite_score')
        comment_plot = plot_to_base64(sentiment_viz, df_com, plot_type=None)

        df['title'] = df.apply(lambda row: f'<a href="{row["video_link"]}" target="_blank">{row["title"]}</a>', axis=1)
        df = df.drop(columns=['video_link'])

        return df, total_plot, comment_plot, engagement_rate_plot, composite_score_plot
    except KeyError as e:
        print(f"Missing expected data in the DataFrame: {e}")
        return None
    except Exception as e:
        print(f"An error occurred while processing the data: {e}")
        return None

def plot_to_base64(plot_func, df, plot_type):
    img = io.BytesIO()
    if plot_type is not None:
        plot_func(df, plot_type=plot_type)
    else:
        plot_func(df)
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')

def strip_emojis(text):
    emoji_pattern = re.compile(
        "[" u"\U0001F600-\U0001F64F" 
        u"\U0001F300-\U0001F5FF"  
        u"\U0001F680-\U0001F6FF"  
        u"\U0001F1E0-\U0001F1FF" 
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)


