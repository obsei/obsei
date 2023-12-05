## Demo UI

This is a minimal UI that can spin up to test Obsei. It's based on streamlit and is very easy to extend for your own use.

![Screenshot](https://raw.githubusercontent.com/obsei/obsei-resources/master/images/obsei-ui-demo.png)

## Usage

### Option 1: Local
Execute in this folder:
```shell
pip install -r requirements.txt
streamlit run Home.py
```

### Option 2: Container

Just run
```
docker run -d --name obesi-ui -p 8501:8501 obsei/obsei-ui-demo
```
You can find the UI at `http://localhost:8501`
