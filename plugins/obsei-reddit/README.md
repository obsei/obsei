# obsei-reddit

Community plugin: subreddit posts, comments and searches through Reddit's public RSS feeds. No API
key, low volume; for higher volume or full threads use the official Reddit API with the `rest`
source and your own OAuth token. Respect Reddit's terms and rate limits.

```yaml
plugins: [reddit]
pipelines:
  - name: community
    sources:
      - key: r-android
        type: reddit
        config: {subreddit: androidapps, query: "obsei OR feedback", kind: search}
```
