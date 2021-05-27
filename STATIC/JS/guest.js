const webexsdk = Webex.init({
  credentials: {
    access_token: guest_token
  }
});

webexsdk.messages.listen().then(() => {
    webexsdk.messages.on('created', (message) => {
        if(message.data.roomType == "group"){
            $(`#${message.data.roomId}`).parent().prependTo("#rooms");
            $(`#${message.data.roomId}`).next().removeClass("hidden");

            var room_name = $(`#${message.data.roomId}`).html();
            var msg = message.data.text;
            $('#noti-room-name').html(room_name);
            $('#noti-msg').html(msg);
            $('.toast').removeClass("hidden");
            setTimeout(function(){
                closeToast()
            }, 10000)
        }
    });
}).catch(reason => {
    console.log(reason);
});

function startRoomWidget(roomId){
    $("tr.active").removeClass("active");
    $(`#${roomId}`).next().addClass("hidden");

    var widget_div = document.getElementById('room-widget');

    webex.widget(widget_div).remove();

    webexsdk.memberships.list({roomId: roomId}).then((membership) => {
        if(membership.length <= 3){
            // Init a new widget
            webex.widget(widget_div).spaceWidget({
                accessToken: guest_token,
                destinationType: 'spaceId',
                destinationId: roomId,
                spaceActivities: { "files": true, "meet": true, "message": true, "people": true },
                initialActivity: 'message',
                secondaryActivitiesFullWidth: false,
                composerActions: { "attachFiles": true }
            });
        }else{
            // Init a new widget
            webex.widget(widget_div).spaceWidget({
                accessToken: guest_token,
                destinationType: 'spaceId',
                destinationId: roomId,
                spaceActivities: { "files": true, "meet": false, "message": true, "people": true },
                initialActivity: 'message',
                secondaryActivitiesFullWidth: false,
                composerActions: { "attachFiles": true }
            });

            setTimeout(function(){
                $('.webex-tabs').append(`
                  <span id="overridden-meet" class="webex-tab-meet">
                    <button class="md-button md-button--circle md-button--25 md-button--green" id="overridden-meet-btn" onclick="customizedMeet('${roomId}')" type="button" aria-label="Call" tabindex="0">
                        <span class="md-button__children" style="opacity: 1;">
                            <i class="md-icon icon icon-camera_16" style="font-size: 16px; padding-right: inherit;"></i>
                        </span>
                    </button>
                </span>`);
            }, 3000);

        }
    });
}

function closeToast(){
    $('.toast').addClass("hidden");
}

function selectGuest(name, id){
    var searchbar = $('#searchbar').val();
    var connect_ids = $('#connect-ids').val();
    if(searchbar.includes(`,${name}`)){
        searchbar = searchbar.replace(`,${name}`, "");
        connect_ids = connect_ids.replace(`,${id}`, "");
    }else if(searchbar.includes(`${name},`)){
        searchbar = searchbar.replace(`${name},`, "");
        connect_ids = connect_ids.replace(`${id},`, "");
    }else if(searchbar.includes(name)){
        searchbar = searchbar.replace(name, "");
        connect_ids = connect_ids.replace(id, "");
    }else{
        if(searchbar == ""){
            searchbar = name;
            connect_ids = id;
        }else{
            searchbar += `,${name}`;
            connect_ids += `,${id}`;
        }
    }
    $('#searchbar').val(searchbar);
    $('#connect-ids').val(connect_ids);
}

// custom logic for multi-party meeting
function customizedMeet(roomId){
    console.log(roomId);
    // Alvin: create a new room
    $.ajax({
        type: "POST",
        url: "/connect_guest", // Alvin: change URL
        data: {
            "connect_ids": $('#connect-ids').val()
        },
        success: function(res){
            // response from POST /connect_guest
            // successful upon creating a new room
            var new_room_id = res;
            var widget_div = document.getElementById('room-widget');
            webex.widget(widget_div).remove();

            // Init a new widget
            webex.widget(widget_div).spaceWidget({
                accessToken: guest_token,
                destinationType: 'spaceId',
                destinationId: new_room_id,
                spaceActivities: { "files": true, "meet": true, "message": true, "people": true },
                initialActivity: 'message',
                secondaryActivitiesFullWidth: false,
                composerActions: { "attachFiles": true }
            });
        }
    });

}

function customLogic(){
    $.ajax({
        type: "POST",
        url: "/connect_guest",
        data: {
            "connect_ids": $('#connect-ids').val()
        },
        success: function(res){
            // response from POST /connect_guest
            if(res == "200"){
                location.reload();
            }
        }
    });
}
