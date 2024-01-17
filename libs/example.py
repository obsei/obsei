# from facebook_scraper import get_profile
# # get_profile("zuck") 
# get_profile("zuck", cookies="libs/cookies.txt")

import facebook_scraper as fs

# get POST_ID from the URL of the post which can have the following structure:
# https://www.facebook.com/USER/posts/POST_ID
# https://www.facebook.com/groups/GROUP_ID/posts/POST_ID
POST_ID = "pfbid02NsuAiBU9o1ouwBrw1vYAQ7khcVXvz8F8zMvkVat9UJ6uiwdgojgddQRLpXcVBqYbl"

# number of comments to download -- set this to True to download all comments
MAX_COMMENTS = 100

# get the post (this gives a generator)
gen = fs.get_posts(
    post_urls=[POST_ID],
    options={"comments": MAX_COMMENTS, "progress": True},
    cookies="libs/cookies.txt"
)

# take 1st element of the generator which is the post we requested
post = next(gen)

# extract the comments part
comments = post['comments_full']

# process comments as you want...
for comment in comments:

    # e.g. ...print them
    print(comment)

    # e.g. ...get the replies for them
    for reply in comment['replies']:
        print(' ', reply)