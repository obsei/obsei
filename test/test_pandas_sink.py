from obsei.payload import TextPayload
from obsei.sink.pandas_sink import PandasSink, PandasSinkConfig


def test_pandas_sink_appends_rows_with_supported_pandas_api():
    config = PandasSinkConfig()
    responses = [
        TextPayload(processed_text="first", source_name="Test"),
        TextPayload(processed_text="second", source_name="Test"),
    ]

    result = PandasSink().send_data(responses, config)

    assert result[["processed_text", "source_name"]].to_dict("records") == [
        {"processed_text": "first", "source_name": "Test"},
        {"processed_text": "second", "source_name": "Test"},
    ]


def test_pandas_sink_filters_included_columns():
    config = PandasSinkConfig(include_columns_list=["processed_text"])

    result = PandasSink().send_data(
        [TextPayload(processed_text="first", source_name="Test")],
        config,
    )

    assert result.to_dict("records") == [{"processed_text": "first"}]
