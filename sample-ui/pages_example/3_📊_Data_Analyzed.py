# Copyright 2018-2022 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import streamlit as st
import inspect
import textwrap
import pandas as pd
import altair as alt
from utils import show_code
from database import *
from utils import *

from urllib.error import URLError

from IPython.display import HTML

def data_frame():
    def make_clickable(val):
        return '<a href="{}">{}</a>'.format(val, val)

    # @st.cache_resource
    def get_data_analyzed():
        results = database.data_analyzed.aggregate([
            {
                '$lookup': {
                    'from': 'urls',
                    'localField': 'url_id',
                    'foreignField': '_id',
                    'as': 'joined_data'
                }
            },
            {
                '$unwind': '$joined_data'  # Optional: Unwind the joined array if needed
            }
        ])

        arrays = []
        counter = 0
        for record in results:
            url = ''
            keyword = ''
            if 'joined_data' in record:
                url = record['joined_data']['url']
                if 'keyword' in record['joined_data']:
                    keyword = record['joined_data']['keyword']

            counter += 1
            record['_id'] = counter
            record['url'] = url
            record['keyword'] = keyword
            del record['joined_data']
            del record['meta_text']
            del record['meta_comment_id']
            del record['meta_photo']
            del record['url_id']
            del record['source_name']
            arrays.append(record)

        df = pd.DataFrame(arrays)
        df.style.format(make_clickable)

        HTML(df.to_html(escape=False))

        return df.set_index('title')

    try:
        df = get_data_analyzed()

        analyzers = st.multiselect(
            "Choose Analyzer", list(set(list(df.index))), [list(set(list(df.index)))[0]]
        )

        # analyzer_urls = st.multiselect(
        #     "Choose URLs", list(set(list(df.index))), ['1']
        # )
        if not analyzers:
            st.error("Please select at least one analyzer.")
        else:
            data = df.loc[analyzers]
            # data /= 1000000.0
            st.write("### Data comment analyzed", data.sort_index())

            # data = data.T.reset_index()
            # data = pd.melt(data, id_vars=["index"]).rename(
            #     columns={"index": "year", "value": "Gross Agricultural Product ($B)"}
            # )
            # chart = (
            #     alt.Chart(data)
            #     .mark_area(opacity=0.3)
            #     .encode(
            #         x="year:T",
            #         y=alt.Y("Gross Agricultural Product ($B):Q", stack=None),
            #         color="Region:N",
            #     )
            # )
            # st.altair_chart(chart, use_container_width=True)
    except URLError as e:
        st.error(
            """
            **This UI requires internet access.**
            Connection error: %s
        """
            % e.reason
        )


st.set_page_config(page_title="Data Analyzed", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.markdown("# Data Analyzed")
st.markdown(
    get_icon_name("Data Analysis"), unsafe_allow_html=True
)

st.sidebar.header("Data Analyzed")
# st.set_page_config(page_title="Data Analyzed", )

# st.write(
#     """This demo shows how to use `st.write` to visualize Pandas DataFrames.
# (Data courtesy of the [UN Data Explorer](http://data.un.org/Explorer.aspx).)"""
# )

data_frame()

# show_code(data_frame)
