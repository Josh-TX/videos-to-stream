sub init()
    ' REPLACE THIS WITH YOUR ACTUAL URL
    hlsUrl = "http://192.168.1.5:3000/playlist.m3u8"

    m.video = m.top.findNode("videoPlayer")
    m.errorLabel = m.top.findNode("errorLabel")
    m.sourceLabel = m.top.findNode("sourceLabel")
    m.sourceLabel.text = "loading stream from " + chr(10) + hlsUrl
    m.video.observeField("state", "onVideoStateChange")
    m.video.observeField("errorMsg", "onVideoError")
    m.video.setFocus(true)
    content = CreateObject("roSGNode", "ContentNode")
    content.url = hlsUrl
    content.title = "HLS Stream"
    content.streamFormat = "hls"
    m.video.content = content
    m.video.control = "play"
    print "MainScene: Playing HLS stream: " + hlsUrl
end sub

sub onVideoStateChange()
    state = m.video.state
    
    if state = "playing"
        m.sourceLabel.visible = false
        m.errorLabel.visible = false
        
    else if state = "error"
        m.errorLabel.visible = true
        print "MainScene: Video playback error"
        
    else if state = "buffering"
        m.errorLabel.visible = false
        
    else if state = "finished"
        print "MainScene: Video playback finished"
        
    end if
end sub

sub onVideoError()
    errorMsg = m.video.errorMsg
    print "MainScene: Video error: " + errorMsg
    m.loadingLabel.visible = false
    m.errorLabel.visible = true
    m.errorLabel.text = "Error: " + errorMsg
end sub