FROM python:3.11-slim

WORKDIR /home/user

RUN apt-get update && apt-get install -y --no-install-recommends curl pkg-config cmake git g++ \
    && apt-get clean autoclean && apt-get autoremove -y \
    && rm -rf /var/lib/{apt,dpkg,cache,log}/

COPY requirements.txt /home/user/

RUN pip install --no-cache-dir -r requirements.txt

COPY ui.py /home/user/
COPY utils.py /home/user/
COPY config.yaml /home/user/

EXPOSE 8501

CMD ["streamlit", "run", "ui.py"]
