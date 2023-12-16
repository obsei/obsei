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
    @st.cache_resource
    def get_data_analyzed():
        results = database['data_analyzed'].find({}, {
            'processed_text',
            'segmented_data_classifier_data_positive',
            'segmented_data_classifier_data_negative',
            'meta_comment_id',
            'meta_text',
            'meta_time',
            'meta_author',
            'meta_channel',
            'meta_votes',
            'meta_photo',
            'meta_heart',
            'source_name',
        })
        arrays = []
        counter = 0
        for record in results:
            counter += 1
            record['_id'] = counter
            arrays.append(record)

        df = pd.DataFrame(arrays)

        df['meta_photo'] = df['meta_photo'].apply(lambda x: f'<img src="{x}" style="max-height:124px;">')

        HTML(df.to_html(escape=False))

        return df.set_index("source_name")

    try:
        df = get_data_analyzed()

        analyzers = st.multiselect(
            "Choose Analyzer", list(set(list(df.index))), ['YoutubeScrapper']
        )
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
            **This demo requires internet access.**
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
