FROM apify/actor-python-playwright:3.12

COPY . ./

RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium --with-deps

CMD ["python", "-m", "src"]
