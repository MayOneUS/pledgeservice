function SetTweet(){
    var tweets = ["tweet1", "tweet2", "tweet3", "tweet4"]
    var tweet = tweets[Math.random()*tweets.length|0]
    document.getElementsByClassName('twitter')[0].href = "https://twitter.com/home?status=" + tweet;
}
