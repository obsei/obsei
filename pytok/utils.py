from datetime import datetime
import json
import os
import re

import pandas as pd
import tqdm

LOGGER_NAME: str = "PyTok"

def update_if_not_none(dict1, dict2):
    dict1.update((k,v) for k,v in dict2.items() if v is not None)
    return dict1

def _get_comment_features(comment):
    comment_user = comment['user']
    if isinstance(comment_user, str):
        raise ValueError()
    elif isinstance(comment_user, dict):
        if 'unique_id' in comment_user:
            author_id = comment_user['uid']
            author_name = comment_user['unique_id']
        elif 'uniqueId' in comment_user:
            author_id = comment_user['id']
            author_name = comment_user['uniqueId']
        else:
            author_name = ''
            author_id = comment_user['uid']
    else:
        raise ValueError()

    mentioned_users = [info['user_id'] for info in comment['text_extra'] if info['user_id'] != '']

    return author_id, author_name, mentioned_users

def load_comment_df_from_files(file_paths):
    comments = []
    for file_path in tqdm.tqdm(file_paths):

        if not os.path.exists(file_path):
            continue

        with open(file_path, 'r') as f:
            comments = json.load(f)
        comments.extend(comments)

    return get_comment_df(comments)

def get_comment_df(comments):
    comments_data = []
    for comment in comments:

        try:
            author_id, author_name, mentioned_users = _get_comment_features(comment)
        except ValueError:
            continue

        comment_replies = comment.get('reply_comment', None)
        if comment_replies:
            for reply_comment in comment_replies:
                try:
                    reply_author_id, reply_author_name, reply_mentioned_users = _get_comment_features(reply_comment)
                except ValueError:
                    continue

                comments_data.append((
                    reply_comment['cid'],
                    datetime.utcfromtimestamp(reply_comment['create_time']), 
                    reply_author_name,
                    reply_author_id, 
                    reply_comment['text'],
                    reply_mentioned_users,
                    reply_comment['aweme_id'],
                    reply_comment['comment_language'],
                    reply_comment['digg_count'],
                    comment['cid']
                ))

        comments_data.append((
            comment['cid'],
            datetime.utcfromtimestamp(comment['create_time']), 
            author_name,
            author_id, 
            comment['text'],
            mentioned_users,
            comment['aweme_id'],
            comment['comment_language'],
            comment['digg_count'],
            None
        ))

    comment_df = pd.DataFrame(comments_data, columns=['comment_id', 'createtime', 'author_name', 'author_id', 'text', 'mentions', 'video_id', 'comment_language', 'like_count', 'reply_comment_id'])
    comment_df = comment_df.drop_duplicates('comment_id')
    comment_df = comment_df[comment_df['text'].notna()]
    comment_df = comment_df[comment_df['video_id'].notna()]
    comment_df = comment_df[comment_df['mentions'].notna()]
    comment_df['text'] = comment_df['text'].str.replace(r'\n',  ' ', regex=True)
    comment_df['text'] = comment_df['text'].str.replace(r'\r',  ' ', regex=True)
    return comment_df

def try_load_comment_df_from_file(file_path, file_paths=[]):
    assert file_path.endswith('.parquet.gzip') or file_path.endswith('.csv'), "File path must be a parquet or csv file"

    if os.path.exists(file_path):
        if file_path.endswith('.csv'):
            comment_df = pd.read_csv(file_path)
        elif file_path.endswith('.parquet.gzip'):
            comment_df = pd.read_parquet(file_path)
        comment_df[['comment_id', 'author_name', 'author_id', 'text', 'video_id', 'comment_language', 'reply_comment_id']] = comment_df[['comment_id', 'author_name', 'author_id', 'text', 'video_id', 'comment_language', 'reply_comment_id']].astype(str)
        comment_df['mentions'] = comment_df['mentions'].apply(_str_to_list)
        comment_df['createtime'] = pd.to_datetime(comment_df['createtime'])
        comment_df['createtime'] = comment_df['createtime'].astype('datetime64[ns]')
    else:
        if not file_paths:
            raise ValueError(f"Parquet file: {file_path} does not exist, and no file paths provided to generate dataframe")

        comment_df = load_comment_df_from_files(file_paths)

        if file_path.endswith('.csv'):
            comment_df.to_csv(file_path, index=False)
        elif file_path.endswith('.parquet.gzip'):
            comment_df.to_parquet(file_path, compression='gzip', index=False)

    return comment_df


def _str_to_list(stri):
    if ',' not in stri:
        return []
    return [word.strip()[1:-1] for word in stri[1:-1].split(',')]

def try_load_video_df_from_file(file_path, file_paths=[]):
    assert file_path.endswith('.parquet.gzip') or file_path.endswith('.csv'), "File path must be a parquet or csv file"
    if os.path.exists(file_path):
        if file_path.endswith('.csv'):
            video_df = pd.read_csv(file_path)
        elif file_path.endswith('.parquet.gzip'):
            video_df = pd.read_parquet(file_path)
        
        video_df[['video_id', 'author_name', 'author_id', 'desc', 'share_video_id', 'share_video_user_id', 'share_type']] = video_df[['video_id', 'author_name', 'author_id', 'desc', 'share_video_id', 'share_video_user_id', 'share_type']].astype(str)
        video_df['createtime'] = pd.to_datetime(video_df['createtime'])
        video_df['mentions'] = video_df['mentions'].apply(_str_to_list)
        video_df['hashtags'] = video_df['hashtags'].apply(_str_to_list)
        return video_df

    else:
        if not file_paths:
            raise ValueError(f"File: {file_path} does not exist, and no file paths provided to generate dataframe")

        videos = []
        for file_path in file_paths:
            with open(file_path, 'r') as f:
                file_data = json.load(f)

            if type(file_data) == list:
                videos += file_data
            elif type(file_data) == dict:
                videos.append(file_data)
            else:
                raise ValueError()
            
        video_df = get_video_df(videos)
        if file_path.endswith('.csv'):
            video_df.to_csv(file_path, index=False)
        elif file_path.endswith('.parquet.gzip'):
            video_df.to_parquet(file_path, compression='gzip', index=False)
        return video_df

def extract_video_features(video):
    # get text extra relating to user names
    video_mentions = [extra for extra in video.get('textExtra', []) if extra.get('userId', None) and extra['userId'] != '0']

    # get all hashtags used in the description
    hashtags = [extra['hashtagName'] for extra in video.get('textExtra', []) if extra.get('hashtagName', None)]

    # get all reply types
    match = re.search("^\#([^# ]+) [^@# ]+ @([^ ]+)", video['desc'])
    if match and len(video_mentions) > 0:
        # if there are multiple mentions we get the first
        if video_mentions[0]['awemeId'] != '':
            share_video_id = video_mentions[0]['awemeId']
        elif video.get('duetInfo', None) and video['duetInfo']['duetFromId'] != '0':
            share_video_id = video['duetInfo']['duetFromId']
        else:
            # no way to get shared video id
            share_video_id = None
        
        share_video_user_id = video_mentions[0]['userId']
        share_video_user_name = video_mentions[0]['userUniqueId']
        share_type = match.group(1)

        video_mentions = video_mentions[1:]
    else:
        share_video_id = None
        share_video_user_id = None
        share_video_user_name = None
        share_type = None

    # get duets that we didn't get with the regex
    if video.get('duetFromId', None) and video['duetFromId'] != '0' and not share_video_id:
        duet_infos = [mention for mention in video_mentions if mention['awemeId'] == video['duetInfo']['duetFromId']]
        # sometimes the awemeId is missing
        if duet_infos:
            duet_info = duet_infos[0]
            share_video_id = duet_info['awemeId']
        else:
            duet_info = video_mentions[0]
            share_video_id = video['duetInfo']['duetFromId']
        
        share_video_user_id = duet_info['userId']
        share_video_user_name = duet_info['userUniqueId']
        share_type = 'duet'

        video_mentions = [mention for mention in video_mentions if mention['awemeId'] != video['duetInfo']['duetFromId']]

    # get user mentions
    mentions = []
    if len(video_mentions) > 0:
        mentions = [mention['userId'] for mention in video_mentions]

    if video.get('duetInfo', None) and video['duetInfo']['duetFromId'] != '0' and share_video_id and video['duetInfo']['duetFromId'] != share_video_id:
        raise ValueError("Comment metadata is mismatched")

    vid_features = (
        video['id'],
        datetime.utcfromtimestamp(int(video['createTime'])), 
        video['author']['uniqueId'], 
        video['author']['id'],
        video['desc'], 
        hashtags,
        share_video_id,
        share_video_user_id,
        share_video_user_name,
        share_type,
        mentions,
        video['stats']['diggCount'],
        video['stats']['shareCount'],
        video['stats']['commentCount'],
        video['stats']['playCount'],
    )
    return vid_features

def get_video_df(videos):
    vids_data = []
    for video in videos:
        vid_features = extract_video_features(video)
        vids_data.append(vid_features)

    video_df = pd.DataFrame(vids_data, columns=[
        'video_id', 'createtime', 'author_name', 'author_id', 'desc', 'hashtags',
        'share_video_id', 'share_video_user_id', 'share_video_user_name', 'share_type', 'mentions',
        'digg_count', 'share_count', 'comment_count', 'view_count'
    ])
    
    return video_df


def try_load_user_df_from_file(file_path, file_paths=[]):
    assert file_path.endswith('.parquet.gzip') or file_path.endswith('.csv'), "File path must be a parquet or csv file"

    if os.path.exists(file_path):
        if file_path.endswith('.csv'):
            user_df = pd.read_csv(file_path)
        elif file_path.endswith('.parquet.gzip'):
            user_df = pd.read_parquet(file_path)

        user_df['id'] = user_df['id'].astype(str)
        user_df['num_following'] = user_df['num_following'].astype('Int64')
        user_df['num_followers'] = user_df['num_followers'].astype('Int64')
        user_df['num_videos'] = user_df['num_videos'].astype('Int64')
        user_df['num_likes'] = user_df['num_likes'].astype('Int64')
        user_df['createtime'] = pd.to_datetime(user_df['createtime'])
        return user_df

    else:
        if not file_paths:
            raise ValueError(f"File: {file_path} does not exist, and no file paths provided to generate dataframe")

        entities = []
        for file_path in tqdm.tqdm(file_paths):
            if not os.path.exists(file_path):
                continue

            with open(file_path, 'r') as f:
                file_data = json.load(f)

            if isinstance(file_data, list):
                entities += file_data
            else:
                raise ValueError()
            
        user_df = get_user_df(entities)
        # protect against people with \r as nickname, how dare they
        if file_path.endswith('.csv'):
            user_df.to_csv(file_path, index=False, lineterminator="\r\n")
        elif file_path.endswith('.parquet.gzip'):
            user_df.to_parquet(file_path, compression='gzip', index=False)
        return user_df

def get_user_df(entities):
    users = {} 
    for entity in entities:
        if 'user' in entity:
            user_info = entity['user']
            if isinstance(user_info, dict):
                if 'unique_id' not in user_info:
                    continue

                user_id = user_info['unique_id']
                if user_id in users:
                    users[user_id] = update_if_not_none(users[user_id], user_info)
                else:
                    users[user_id] = user_info

            elif isinstance(user_info, str):
                if user_info not in users:
                    users[user_id] = {'unique_id': user_info}

        elif 'author' in entity:
            user_info = entity['author'] | entity['authorStats']

            user_id = user_info['uniqueId']
            if user_id in users:
                users[user_id] = update_if_not_none(users[user_id], user_info)
            else:
                users[user_id] = user_info
        
        elif 'followerCount' in entity:
            user_info = entity
            user_id = user_info['uniqueId']
            if user_id in users:
                users[user_id] = update_if_not_none(users[user_id], user_info)
            else:
                users[user_id] = user_info

        elif 'userInfo' in entity:
            user_info = entity['userInfo']['user']
            user_info.update(entity['userInfo']['stats'])
            user_id = user_info['uniqueId']
            if user_id in users:
                users[user_id] = update_if_not_none(users[user_id], user_info)
            else:
                users[user_id] = user_info

        else:
            raise ValueError("Unknown entity type")

    assert len(users) > 0, "No users found in entities"

    user_df = pd.DataFrame(list(users.values()))

    if 'unique_id' in user_df.columns:
        user_df['uniqueId'] = user_df['unique_id'].combine_first(user_df['uniqueId'])
        user_df = user_df.drop(columns=['unique_id'])

    user_df = user_df.drop_duplicates('uniqueId')

    if 'uid' in user_df.columns:
        user_df['id'] = user_df['id'].combine_first(user_df['uid'])
        user_df = user_df.drop(columns=['uid'])

    # thank you dfir!!! https://dfir.blog/tinkering-with-tiktok-timestamps/
    user_df.loc[user_df['id'].notna(), 'createtime'] = user_df.loc[user_df['id'].notna(), 'id'].apply(lambda x: datetime.utcfromtimestamp(int(x) >> 32))
    user_df['createtime'] = pd.to_datetime(user_df['createtime'], utc=True)
    user_df[['followingCount', 'followerCount', 'videoCount', 'diggCount']] = user_df[['followingCount', 'followerCount', 'videoCount', 'diggCount']].astype('Int64')
    # excluding because it messes up the csv and its not accessible anyway
    # user_df['avatarThumb'] = user_df['avatarThumb'].combine_first(user_df['avatar_thumb'])
    if 'avatar_thumb' in user_df.columns:
        user_df = user_df.drop(columns=['avatar_thumb'])
    user_df = user_df[['id', 'uniqueId', 'nickname', 'signature', 'verified', 'followingCount', 'followerCount', 'videoCount', 'diggCount', 'createtime']]
    user_df = user_df.rename(columns={
        'uniqueId': 'unique_id',
        'followingCount': 'num_following', 
        'followerCount': 'num_followers', 
        'videoCount': 'num_videos', 
        'diggCount': 'num_likes'
    })
    
    return user_df