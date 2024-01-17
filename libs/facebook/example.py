
import libs.facebook as fs

# get POST_ID from the URL of the post which can have the following structure:
# https://www.facebook.com/USER/posts/POST_ID
# https://www.facebook.com/groups/GROUP_ID/posts/POST_ID
POST_ID = "https://www.facebook.com/LaoMo.VN/posts/pfbid02DFNTUPyPRh8EUTehKZ4BKbeeorCkA8Gx4r52XHBmQGXk5JxWEfMwrAANNuojdkYDl"
#1 # GROUP_ID = "1859820851144571"
# GROUP_ID = "763107807482553"
# number of comments to download -- set this to True to download all comments
MAX_COMMENTS = 100

gen = fs.get_posts(
    # account='nam.tong36',
    # group=GROUP_ID,
    # post_urls=["336280019220590"],
    post_urls=['https://www.facebook.com/photo/?fbid=719253296969094&set=a.524065426487883'],
    options={"comments": MAX_COMMENTS, "progress": True},
    cookies='cookies.txt'
)

# take 1st element of the generator which is the post we requested
post = next(gen)

# profie = fs.get_friends('nam.tong36',
#                # cookies='libs/facebook/cookies.txt'
#                )
# # for c in profie:
# #     print(c, '<<<<<<<,,,')
# print(post, profie, '================')

# extract the comments part
comments = post['comments_full']

# process comments as you want...
for comment in comments:

    # e.g. ...print them
    print(comment)

    # e.g. ...get the replies for them
    for reply in comment['replies']:
        print(' ', reply)

