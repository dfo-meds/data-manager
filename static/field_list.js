
var current_num = 1;

function remove_item_from_list(list_item) {
    let list = list_item.parent();
    let children = list.find("li").length;
    if (children <= 1) {
        window.alert("Cannot remove an item when there is only one item.");
    }
    else {
        let id = list_item.find("label").attr("for");
        let last_pos = id.lastIndexOf("-");
        let id_num = parseInt(id.slice(last_pos + 1));
        if (id_num < (children - 1)) {
            list.find("li").each(function() {
                let local_id = $(this).find("label").attr("for");
                let local_last_pos = local_id.lastIndexOf("-");
                let front_part = local_id.slice(0, local_last_pos);
                let local_id_num = parseInt(local_id.slice(local_last_pos + 1));
                if (local_id_num > id_num) {
                    new_id = front_part + "-" + (local_id_num - 1)
                    $(this).find("label").attr("for", new_id);
                    $(this).find("input").attr("id", new_id);
                    $(this).find("input").attr("name", new_id);
                }
            });
        }
        list_item.remove();
    }
}

$(document).ready(function() {
    $("div.form-field-field-list").each(function() {
        let button_id = "form_button_" + current_num
        $(this).find(".form-control").append("<div class='add-button'><a id='" + button_id + "'>" + add_item_text + "</a></div>");
        $("#" + button_id).click(function() {
            let update_list = $(this).parent().parent().find("ul");
            let update_example = update_list.find("li:first").clone();
            let item_count = update_list.find("li").length;
            update_example.find("[id]").each(function() {
                id_tag = $(this).attr('id');
                if (id_tag.indexOf("-0-") >= 0) {
                    $(this).attr('id', id_tag.replace("-0-", "-" + item_count.toString() + "-"));
                }
                else if (id_tag.substring(id_tag.length - 2) == "-0") {
                    $(this).attr('id', id_tag.substring(0, id_tag.length - 2) + "-" + item_count.toString());
                }
            })
            update_example.find("[for]").each(function() {
                id_tag = $(this).attr('for');
                if (id_tag.indexOf("-0-") >= 0) {
                    $(this).attr('for', id_tag.replace("-0-", "-" + item_count.toString() + "-"));
                }
                else if (id_tag.substring(id_tag.length - 2) == "-0") {
                    $(this).attr('for', id_tag.substring(0, id_tag.length - 2) + "-" + item_count.toString());
                }
            })
            update_example.find("[name]").each(function() {
                id_tag = $(this).attr('name');
                if (id_tag.indexOf("-0-") >= 0) {
                    $(this).attr('name', id_tag.replace("-0-", "-" + item_count.toString() + "-"));
                }
                else if (id_tag.substring(id_tag.length - 2) == "-0") {
                    $(this).attr('name', id_tag.substring(0, id_tag.length - 2) + "-" + item_count.toString());
                }
            })
            update_example.find(".remove-button").remove();
            update_example.find("textarea").text('');
            update_example.find("input").val('');
            let button_id = "form_button_" + current_num;
            update_example.prepend("<div class='remove-button'><a id='" + button_id + "'>-</a><br class='cb' /></div>");
            update_list.append(update_example);
            $("#" + button_id).click(function() {
                remove_item_from_list($(this).parent().parent());
            });
            current_num += 1;
        });
        current_num += 1;
        $(this).find(".form-control li").each(function() {
            let button_id = "form_button_" + current_num;
            $(this).prepend("<div class='remove-button'><a id='" + button_id + "'>-</a><br class='cb' /></div>");
            $("#" + button_id).click(function() {
                remove_item_from_list($(this).parent().parent());
            });
            current_num += 1;
        });
    });
});
