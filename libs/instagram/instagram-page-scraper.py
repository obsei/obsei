
import instaloader
import random
import time
import csv

def login_to_instagram(username, password):
    loader = instaloader.Instaloader()

    try:
        # edit cookie in instaloadercontext.py line 251 if scrapper error
        loader.login(username, password)
        print("Login successful!")
        return loader
    except instaloader.exceptions.BadCredentialsException:
        print("Invalid login credentials!")
        return None

def scrape_instagram_post(loader, shortcode):
    if loader is None:
        return

    with open('SEresult.csv', 'a+', newline='', encoding='utf-8') as file:
      writer = csv.writer(file)
      try:
          post = instaloader.Post.from_shortcode(loader.context, shortcode)

          # Access the post data
          print("Post ID:", post.mediaid)
          time.sleep(random.uniform(2, 3))
          postid = post.mediaid
          print("Caption:", post.caption)
          time.sleep(random.uniform(2, 3))
          caption = post.caption
          print("Likes:", post.likes)
          time.sleep(random.uniform(2, 3))
          likes = post.likes
          writer.writerow(["post.ID", "Caption", "Likes"])
          writer.writerow([postid, caption, likes])

          # Scrape and print the comments
          print("Comments:")
          writer.writerow(["Username", "Comment"])
          for comment in post.get_comments():
              print(comment, '=============')
              print("Username:", comment.owner.username)
              time.sleep(random.uniform(2, 3))
              username=comment.owner.username
              print("Comment:", comment.text)
              time.sleep(random.uniform(2, 3))
              comment_user=comment.text
              print("---")
              writer.writerow([username, comment_user])
      except instaloader.exceptions.InstaloaderException as e:
          print("Error occurred while scraping the post:", str(e))




# Replace 'SHORTCODE_HERE' with the actual shortcode of the post
shortcode = 'CsqkhP3vXz6'

# Replace 'YOUR_USERNAME' and 'YOUR_PASSWORD' with your Instagram login credentials
username = 'pong_and_meos'
password = 'T0ngnamm'

loader = login_to_instagram(username, password)
time.sleep(random.uniform(2, 3))  # Sleep for a random duration between 2 and 3 seconds
scrape_instagram_post(loader, shortcode)
