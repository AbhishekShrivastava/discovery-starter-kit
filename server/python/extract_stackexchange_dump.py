#!/usr/bin/env python
#
# Copyright 2016 IBM Corp. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# -*- coding: utf-8 -*-
import xml.etree.ElementTree
import json
import csv
import getopt
import sys
import re

from collections import defaultdict
from collections import OrderedDict

from random import shuffle

from HTMLParser import HTMLParser


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def stripSpecial(myString):
    s = MLStripper()
    s.feed(myString)
    htmlFreeString = s.get_data()
    cleanString = re.sub('/', '\\/', htmlFreeString)
    cleanString = re.sub('<[^>]+>', '', cleanString)
    cleanString = cleanString.replace('\n', ' ').replace('"', ' ') \
        .replace('!', ' ').replace('@', ' ').replace('#', ' ') \
        .replace('$', ' ').replace('%', ' ').replace('^', ' ') \
        .replace('&', ' ').replace('*', ' ').replace('(', ' ') \
        .replace(')', ' ').replace('<', ' ').replace('>', ' ') \
        .replace('/', ' ').replace('\\', ' ').replace('[', ' ') \
        .replace(']', ' ').replace('{', ' ').replace('}', ' ') \
        .replace('|', ' ').replace(':', ' ').replace(';', ' ') \
        .replace(',', ' ').replace('-', ' ').replace('+', ' ') \
        .replace('=', ' ').replace('~', ' ').replace('_', ' ')
    return re.sub(' +', ' ', cleanString)


INPUT_DIR = ''
OUTPUT_DIR = ''
SPLIT_PERCENTAGE = 0.0


def usage():
    print ('extract_stackexchange_dump.py ' +
           '-i <input_content_directory>(required) ' +
           '-o <output_files_directory> ' +
           '-s <split_percentage>')


try:
    opts, args = getopt.getopt(
                    sys.argv[1:],
                    'hdi:o:s:',
                    ['inputfile=', 'outputfile=', 'splitpercentage=']
                 )
except getopt.GetoptError as err:
    sys.exit(2)

for opt, arg in opts:
    if opt == '-h':
        usage()
        sys.exit()
    elif opt in ('-i', '--inputfile'):
        INPUT_DIR = arg
    elif opt in ('-o', '--outputfile'):
        OUTPUT_DIR = arg
    elif opt in ('-s', '--splitpercentage'):
        SPLIT_PERCENTAGE = float(arg)
    elif opt == '-d':
        DEBUG = True

if not INPUT_DIR:
    print ('Required argument missing.')
    usage()
    sys.exit(2)

if not OUTPUT_DIR:
    print ('Output files will be saved in the input directory ' +
           'since an output directory was not provided.')
    OUTPUT_DIR = INPUT_DIR

if SPLIT_PERCENTAGE == 0:
    print ('No train/test tmp specified, ' +
           'will use default of .8 (80% for training, 20% for testing')
    SPLIT_PERCENTAGE = .8


documents = []
responses = []

print('Getting XML...')
print('Getting Posts...')
postsXML = xml.etree.ElementTree.parse(INPUT_DIR+'/Posts.xml').getroot()
print('Posts loaded')
print('Getting Votes...')
votesXML = xml.etree.ElementTree.parse(INPUT_DIR+'/Votes.xml').getroot()
print('Votes loaded')
print('Getting Users...')
usersXML = xml.etree.ElementTree.parse(INPUT_DIR+'/Users.xml').getroot()
print('Users loaded')
print('XML loaded')


def getUserInfo(userId):
    """
    It returns the reputation and the display name of the user passed
    as parameter
    """
    for user in usersXML.findall('row'):
        if (user.get('Id') == userId):
            return user.get('Reputation'), user.get('DisplayName')
    return 0, 0


# Types of votes
# Id | Name
# -- | ----------------------
# 1  | AcceptedByOriginator
# 2  | UpMod
# 3  | DownMod
# 4  | Offensive
# 5  | Favorite
# 6  | Close
# 7  | Reopen
# 8  | BountyStart
# 9  | BountyClose
# 10 | Deletion
# 11 | Undeletion
# 12 | Spam
# 15 | ModeratorReview
# 16 | ApproveEditSuggestion


def getVotes(voteTypeIds):
    """
    Returns a dictionary of dictionaries for all posts and all vote types with
    their counts. It currently takes the list of all vote type ids
    Usage: [postId][voteType] return the count of votes
    """
    print('Starting getVotes...')
    voteTypes = set()
    for voteType in voteTypeIds.split(" "):
        voteTypes.add(int(voteType))
    outerDict = defaultdict(dict)
    innerDict = defaultdict(dict)
    for voteType in voteTypes:
        innerDict[voteType] = 0
    for vote in votesXML.findall('row'):
        # print('Processing Vote id: ' + vote.get('VoteTypeId'))
        voteTypeId = int(vote.get('VoteTypeId'))
        if (voteTypeId in voteTypes):
            postId = int(vote.get('PostId'))
            if postId in outerDict.keys():
                newCount = outerDict[postId][voteTypeId] + 1
                outerDict[postId][voteTypeId] = newCount
            else:
                outerDict[postId] = innerDict.copy()
                outerDict[postId][voteTypeId] = 1
    return outerDict


ANSWER_COUNT_MAX = 0

qa_dict = defaultdict(dict)
votesDict = getVotes("1 2 3 4 5 6 7 8 9 10 11 12 15 16")

indexed_dict = dict()
print('Getting all posts in postsXML...')
for post in postsXML.findall('row'):
    # print('Post Id: ' + post.get('Id'))
    indexed_dict[post.get('Id')] = post

print('Getting all posts in postsXML again...')
for posts in postsXML.findall('row'):
    # print('Post Id: ' + posts.get('Id'))
    if(int(posts.get('PostTypeId')) == 1):
        title = stripSpecial(
                 posts.get('Title').encode('ascii', 'ignore').decode('ascii')
                )
        body = stripSpecial(
                posts.get('Body').encode('ascii', 'ignore').decode('ascii')
               )
        postId = posts.get('Id')
        qa_dict[postId] = defaultdict(dict)
        answerCount = int(posts.get('AnswerCount'))
        if answerCount > ANSWER_COUNT_MAX:
            ANSWER_COUNT_MAX = answerCount
        commentCount = int(posts.get('CommentCount'))
        score = int(posts.get('Score'))
        views = int(posts.get('ViewCount'))
        tags = str(posts.get('Tags'))
        if posts.get('AcceptedAnswerId') is None:
            acceptedAnswerId = 0
        else:
            acceptedAnswerId = int(posts.get('AcceptedAnswerId'))

        documents.append({'id': postId, 'title': title, 'text': body,
                          'answerCount': 0, 'questionScore': score,
                          'acceptedAnswerId': acceptedAnswerId, 'accepted': -1,
                          'views': views, 'tags': tags})

    elif(int(posts.get('PostTypeId')) == 2):
        index = 0
        postId = int(posts.get('Id'))
        parentId = posts.get('ParentId')
        tmp_dict = defaultdict(dict)
        title = ''
        subtitle = ''
        answer = ''
        accepted = 0
        reputation = 0
        upVotes = 0
        downVotes = 0
        if parentId not in qa_dict.keys():
            tmp_dict[postId] = int(posts.get('Score'))
            qa_dict[parentId] = tmp_dict
        else:
            tmp_dict = qa_dict[parentId]
            tmp_dict[postId] = int(posts.get('Score'))
            qa_dict[parentId] = tmp_dict
        for tmp in reversed(documents):
            if(int(tmp.get('id')) == int(parentId)):
                index = documents.index(tmp)
                documents[index].update(
                    {'answer' + str(documents[index].get('answerCount')):
                        posts.get('Body')})
                documents[index].update(
                    {'answerCount':
                        int(documents[index].get('answerCount')) + 1})
                title = documents[index].get('title')
                subtitle = documents[index].get('text')
                views = documents[index].get('views')
                tags = documents[index].get('tags')
                acceptAnswerId = int(documents[index].get('acceptedAnswerId'))
                if int(posts.get('Id')) == acceptAnswerId:
                    documents[index].update(
                        {'accepted':
                            int(documents[index].get('answerCount'))})
                    accepted = 1
                break
        answerScore = posts.get('Score').encode('ascii', 'ignore') \
            .decode('ascii')
        answer = stripSpecial(
                    posts.get('Body').encode('ascii', 'ignore').decode('ascii')
                    )
        subtitle = stripSpecial(
                    subtitle.encode('ascii', 'ignore').decode('ascii')
                    )
        title = stripSpecial(title.encode('ascii', 'ignore').decode('ascii'))
        userId = posts.get('OwnerUserId')
        reputation, username = getUserInfo(userId)
        authorUserId = 0
        if parentId in indexed_dict:
            authorUserId = indexed_dict[parentId].get('OwnerUserId')
        authorReputation, authorUsername = getUserInfo(authorUserId)
        # Getting the number of UpMod votes
        tempDict = votesDict[postId]
        if (2 in tempDict.keys()):
            upVotes = int(tempDict[2])  # UpMod vote type id is 2
        # Getting the number of DownMod votes
        if (3 in tempDict.keys()):
            downVotes = int(tempDict[3])  # DownMod vote type id is 3
        tempDict.clear()
        question = {'title': title, 'subtitle': subtitle}
        item = {'id': postId, 'answerScore': answerScore, 'answer': answer,
                'question': question, 'accepted': accepted,
                'userReputation': int(reputation), 'upModVotes': upVotes,
                'downModVotes': downVotes, 'views': views, 'tags': tags,
                'userId': userId, 'username': username,
                'authorUsername': authorUsername, 'authorUserId': authorUserId}
        # write the file
        output_str = json.dumps(item, sort_keys=True).replace('\n', '')
        f2 = open(OUTPUT_DIR + '/travel_' + str(postId) + '.json', 'w+')
        f2.write(output_str + '\n')
        f2.close()

print ('Ground truth file generated.')

# ordering the dictionary for relevance
for key, value in qa_dict.items():
    qa_dict[key] = OrderedDict(
                    sorted(value.items(), key=lambda x: x[1], reverse=True)
                    )


train_writer = csv.writer(
                open(OUTPUT_DIR+'/answerGT_train.csv', 'wb'),
                delimiter=','
                )
test_writer = csv.writer(
                open(OUTPUT_DIR+'/answerGT_test.csv', 'wb'),
                delimiter=','
                )

validdocuments = []
print ('length of documents: %d ' % len(documents))

questions = 0
filtered = 0
for post in documents:
    tmp_dict = qa_dict[post.get('id')]
    if questions > 3000:
        break
    if len(tmp_dict) > 0:
        validdocuments.append(post)
    else:
        filtered = filtered + 1

print ('number of original documents: %d ' % len(documents))
print ('number of filtered documents: %d ' % filtered)
print ('number of valid documents: %d ' % len(validdocuments))

shuffle(validdocuments)
train_documents = validdocuments[int(
                    len(validdocuments) * (1 - SPLIT_PERCENTAGE)
                    ) + 1:]
test_documents = validdocuments[:int(
                    len(validdocuments) * (1 - SPLIT_PERCENTAGE)
                    )]

print ('length of train documents: %d ' % len(train_documents))
print ('length of test documents: %d ' % len(test_documents))

questions = 0
for post in train_documents:
    tmp_dict = qa_dict[post.get('id')]
    if questions > 3000:
        break
    relevance_list = []
    relevance = 5
    relevance_list.append(
        post.get('title').encode('ascii', 'ignore').decode('ascii')
        )
    for key, value in tmp_dict.items():
        if (relevance > 0):
            relevance_list.append(str(key))
            relevance_list.append(str(relevance))
            relevance = relevance - 1
        else:
            break
    questions = questions + 1
    train_writer.writerow(relevance_list)


for tmp in train_documents:
    del tmp['acceptedAnswerId']

questions = 0
for post in test_documents:
    tmp_dict = qa_dict[post.get('id')]
    if questions > 3000:
        break
    if len(tmp_dict) > 0:
        relevance_list = []
        relevance = 5
        relevance_list.append(
            post.get('title').encode('ascii', 'ignore').decode('ascii')
            )
        for key, value in tmp_dict.items():
            if (relevance > 0):
                relevance_list.append(str(key))
                relevance_list.append(str(relevance))
                relevance = relevance - 1
            else:
                break
        questions = questions + 1
        test_writer.writerow(relevance_list)


for tmp in test_documents:
    del tmp['acceptedAnswerId']
