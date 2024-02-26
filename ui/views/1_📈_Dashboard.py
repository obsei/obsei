from datetime import datetime
import pymongo
import streamlit as st  # web development
import numpy as np  # np mean, np random
import pandas as pd  # read csv, df manipulation
import time  # to simulate a real time data, time loop
import plotly.express as px  # interactive charts
from wordcloud import WordCloud
import altair as alt


df = pd.read_csv("https://raw.githubusercontent.com/Lexie88rus/bank-marketing-analysis/master/bank.csv")

logo_url = "https://raw.githubusercontent.com/obsei/obsei-resources/master/logos/obsei_200x200.png"

st.set_page_config(
    page_title='Real-Time Data Science Dashboard',
    page_icon=logo_url,
    layout='wide'
)
st.markdown("""
    <head>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css"
        rel="stylesheet" integrity="sha384-EVSTQN3/azprG1Anm3QDgpJLIm9Nao0Yz1ztcQTwFspd3yD65VohhpuuCOmLASjC" crossorigin="anonymous">
    </head>
""", unsafe_allow_html=True)
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["obsei"]
collection = db["data_analyzed"]

# read csv from a github repo

# OPTION CONFIG
select_options = st.selectbox("Choose Option",
    ('config 1',
    'config 2',
    'config 3',
    'config 4')
)

# CUSTOM CSS
st.markdown("""
        <style>
            .st-emotion-cache-12jd9a8, .st-emotion-cache-j5r0tf, .st-emotion-cache-12jd9a8 .st-emotion-cache-1wivap2 div p {
                text-align:center;    
            }
            .st-emotion-cache-17c4ue{
                display:block;
            }
            @media (max-width: 650px) {
               .st-emotion-cache-j5r0tf {
                    text-align:center !important;    
                }

            }
            @media (max-width: 1800px){
                 .st-emotion-cache-j5r0tf {
                    text-align:center !important;    
                }
            } 
            
            # @media (max-width: 1300px){
            #     #deckgl-wrapper{
            #         height:527px !important;
            #     }

            # }

        </style>
    """, unsafe_allow_html=True)
# END CUSTOM CSS
# CREATE CONTAINER MENTIONS
with st.container(border=True):
    
    col_ct1, col_ct2, col_ct3, col_ct4, col_ct5 = st.columns(5)
    with col_ct1.container():
        col_ct1.metric(label="Total Comments", value=1000, )
        st.write('<i class="fa-solid fa-message fs-1"></i>',unsafe_allow_html=True)
    with col_ct2.container():
        col_ct2.metric(label="Total Hearts", value=1000)
        st.write('<i class="fa-solid fa-heart fs-1"></i>',unsafe_allow_html=True)
    with col_ct3.container():
        col_ct3.metric(label="Social", value="Youtube")
        st.write('<i class="fa-brands fa-youtube fs-1"></i>',unsafe_allow_html=True)
    with col_ct4.container():
        col_ct4.metric(label="AVG Positive", value=1000)
        st.write('<i class="fa-solid fa-face-smile fs-1"></i>',unsafe_allow_html=True)
    with col_ct5.container():
        col_ct5.metric(label="AVG Negative", value=1000)
        st.write('<i class="fa-solid fa-face-meh fs-1"></i>',unsafe_allow_html=True)
        
with st.container(border=True):
    st.subheader("Total Comments")
    df = pd.DataFrame({
            "Total comment": np.random.randint(0, 101, size=10),
            "date": datetime.now().date()
        })
    st.bar_chart(df.set_index('date')['Total comment'])



data = list(collection.find())


#END CREATE SELECT BOX CHOOSE CONFIG USER
colcmt_chart1,colcmt_chart2 = st.columns(2)
col_table, col_top = st.columns([2,1])
col_lang, col_map = st.columns(2)
cl1_chart, cl2_chart = st.columns([2,1])

with st.container(border=True):
    # TABLE SHOW RECORD
    with col_table.container():
        for item in data:
            del item["url_id"], item["_id"],item["source_name"]
        df = pd.DataFrame(data)
        df["negative"] = df["segmented_data"].apply(lambda x: x["classifier_data"]["negative"])
        df["positive"] = df["segmented_data"].apply(lambda x: x["classifier_data"]["positive"])
        df["author"] = df["meta"].apply(lambda x: x["author"])
        df["channel"] = df["meta"].apply(lambda x: x["channel"])
        df["text"] = df["meta"].apply(lambda x: x["text"])
        df["time"] = df["meta"].apply(lambda x: x["time"])
        df["votes"] = df["meta"].apply(lambda x: x["votes"])
        df["photo"] = df["meta"].apply(lambda x: x["photo"])
        df["heart"] = df["meta"].apply(lambda x: x["heart"])
        # Loại bỏ cột "meta"
        df.drop(columns=["meta"], inplace=True)
        # Loại bỏ cột "segmented_data"
        df.drop(columns=["segmented_data"], inplace=True)
        st.dataframe(df)
    with col_top.container():
        # CREATE CONTAINER TOP
            with st.container(border=True,height=192):
                st.header('Top 10 Commnents')
                for _ in range(10):
                    st.write("hahaha")
            with st.container(border=True,height=192):

                st.header("Top Vote Youtube")
                for _ in range(10):
                    st.write("hahaha")
                    
with st.container():
    # CREATE CONTAINER LANGUAGE
    with col_lang.container(border=True):
        data = {
        'Ngôn ngữ': ['English', 'French', 'Spanish', 'German'],
        'Số lượng': [100, 50, 30, 20]
        }

        # Tạo DataFrame từ dữ liệu mẫu
        df = pd.DataFrame(data)
        st.subheader("Languages")
        # Tạo biểu đồ tròn
        fig = px.pie(df, values='Số lượng', names='Ngôn ngữ')

        # Hiển thị biểu đồ tròn trong Streamlit
        st.plotly_chart(fig,use_container_width=True)
    with col_map.container(border=True):
        st.markdown("### Sentiment")
        # sensitive_percentage = np.random.randint(0, 101, size=10)  # Giả định dữ liệu từ 0 đến 100%
        # negative_percentage = np.random.randint(0, 101, size=10)
        # dates = pd.date_range('2024-02-01', '2024-02-10')

        # sentiment_avg = (sensitive_percentage + negative_percentage) / 2

        # # Tạo DataFrame từ dữ liệu và trung bình cộng
        # df = pd.DataFrame({
        #     'Sensitive': sensitive_percentage,
        #     'Negative': negative_percentage,
        #     'Sentiment': sentiment_avg,
        #     'Date': dates
        # })

        # # Hiển thị biểu đồ cột
        # st.bar_chart(df.set_index('Date')[['Sensitive','Negative']])        
        sensitive_percentage = np.random.randint(0, 101, size=10)  # Giới hạn từ 0 đến 50%
        negative_percentage = 100 - sensitive_percentage
        dates = pd.date_range('2024-02-01', '2024-02-10')

        sentiment_avg = (sensitive_percentage + negative_percentage) / 2

        # Tạo DataFrame từ dữ liệu và trung bình cộng
        df = pd.DataFrame({
            'Positive': sensitive_percentage,
            'Negative': negative_percentage,
            'Sentiment': 100,
            'Date': dates
        })
        df['Positive']=np.random.randint(0, 51, size=10)
        df['Negative']=df['Sentiment']-df['Positive']
        df['Total Sentiment'] = df['Sentiment'] / 2

        # Melt DataFrame để chuyển đổi dạng wide thành long, nhưng giữ cột Sentiment_All
        df_melted = df.melt(id_vars=['Date','Total Sentiment'], value_vars=['Positive', 'Negative'], var_name='Category', value_name='Value')

        # Tạo biểu đồ cột với Altair
        chart = alt.Chart(df_melted).mark_bar().encode(
            x='Date:T',
            y=alt.Y('Total Sentiment:Q',axis=alt.Axis(title='% Total Sentiment'), scale=alt.Scale(domain=[0, 100])),
            color='Category:N'
        ).properties(
            width=700,
            height=450
        )
        st.altair_chart(chart,use_container_width=True)
    with st.container():
        with colcmt_chart1.container(border=True):
            st.subheader("Total Comment")
            df = pd.DataFrame({
                "Total comment": np.random.randint(0, 101, size=10),
                "date": datetime.now().date()
            })
            st.bar_chart(df.set_index('date')['Total comment'])
        with colcmt_chart2.container(border=True):
            st.subheader("Total Heart")
            # data_heart = list(collection.find({}, {"meta_heart": 1, "_id": 0}))

            # Tạo DataFrame từ dữ liệu
            # df = pd.DataFrame(data_heart)
            dates = pd.date_range('2024-02-01', '2024-02-10')
            df = pd.DataFrame({
                "Total heart": np.random.randint(0, 101, size=10),
                "date": dates
            })
            st.bar_chart(df.set_index('date')['Total heart'])

with cl2_chart.container(border=True):

    # emotions = ['Positive', 'Negative', 'Neutral']
    # values = [20, 10, 15]
    # fig, ax = plt.subplots()
    # ax.bar(emotions, values)
    # st.pyplot(fig)
    
    map_option = st.selectbox("Choose Map:", ("Global", "Việt Nam"))

    # Hiển thị bản đồ dựa trên lựa chọn
    df = pd.DataFrame({
        'LATITUDE': [21.0285, 10.7769, 21.0208, 48.8582, 2.2947],
        'LONGITUDE': [105.8542, 106.7009, 105.8475, 2.3490, 46.7711]
    })

    if map_option == "Global":
        st.map(df,size=15,use_container_width=False)
    elif map_option == "Việt Nam":
        vietnam_df = df.loc[df['LONGITUDE'].between(102, 109)]
        st.map(vietnam_df, use_container_width=False)
    

with cl1_chart.container(border=True):
#CLOUD CHART
    st.subheader("Tag Cloud Chart")
    keywords = {
    'data': 100,
    'science': 80,
    'machine': 60,
    'learning': 70,
    'artificial': 50,
    'intelligence': 40
    }

    keyword_list = list(keywords.keys())
    max_words = max(keywords.values())
    wordcloud = WordCloud(width=400, background_color='white').generate_from_frequencies(keywords)

    left_column, right_column = st.columns([1, 2])
    with left_column:
        st.header("Keyword List")
        df = pd.DataFrame(keyword_list, columns=["Keyword"])

        st.dataframe(df,height=445, use_container_width=True)
    with right_column:
        st.header("Word Cloud")
        st.image(wordcloud.to_array(), use_column_width=True)







    
