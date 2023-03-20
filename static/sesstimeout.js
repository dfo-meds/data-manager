
let block_logout = false;
let expiry = 0;
let session_timeout_link = "";
let ajax_refresh_link = "";
let show_window = 600;
let time_box_id = "";
let session_timeout_box_id = "";
let refresh_error = "An unknown error occurred while refreshing your session timeout";

function refresh_session() {
    block_logout = true;
    $.get(ajax_refresh_link, function(data) {
        expiry = Date.now() + (data.extension * 1000);
        block_logout = false;
    }).fail(function() {
        window.alert(refresh_error);
        block_logout = false;
    });
}

function update_timestamp() {
    let left = (expiry - Date.now()) / 1000.0;
    if (left < 0) {
        if (!block_logout) {
            window.location.href = session_timeout_link;
        } else {
            setTimeout(update_timestamp, 1000);
        }
    } else {
        let hours = Math.floor(left / 3600.0);
        let mins = Math.floor((left - (hours * 60.0)) / 60.0);
        let seconds = Math.floor(left - (mins * 60.0) - (hours * 3600.0));
        if (seconds < 10) {
            seconds = "0" + seconds;
        }
        if (mins < 10 && hours > 0) {
            mins = "0" + mins;
        }
        if (hours > 0) {
            $(time_box_id).text(hours + ":" + mins + ":" + seconds);
        } else {
            $(time_box_id).text(mins + ":" + seconds);
        }
        if (left < show_window) {
            $(session_timeout_box_id).removeClass("hidden")
            setTimeout(update_timestamp, 500);
        } else {
            $(session_timeout_box_id).addClass("hidden")
            setTimeout(update_timestamp, left * 500);
        }
    }
}

function start_session_timeout(box_id, time_id, time_remaining_seconds, timeout_link, refresh_link, refresh_error_text, show_time_left_seconds) {
    session_timeout_box_id = box_id;
    time_box_id = time_id;
    session_timeout_link = timeout_link;
    ajax_refresh_link = refresh_link;
    expiry = Date.now() + (time_remaining_seconds * 1000);
    show_window = show_time_left_seconds;
    refresh_error = refresh_error_text;
    setTimeout(update_timestamp, (time_remaining_seconds / 2));

}
