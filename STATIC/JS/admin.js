$(function(){
    $(".save-btn").on("click", function(){
        var this_obj = $(this);
        var allowed_conn_inputs = this_obj.parent().parent().find(".allowed-conn").find("input");
        var allowed_conn = []
        allowed_conn_inputs.each((i, input) => {
            if($(input).prop("checked") == true){
                allowed_conn.push(parseInt($(input).attr("class")));
            }
        });

        $.ajax({
            type: "POST",
            url: "/edit_guest",
            data: {
                "id": this_obj.parent().parent().find(".id").html(),
                "name": this_obj.parent().parent().find(".name").val(),
                "username": this_obj.parent().parent().find(".username").val(),
                "password": this_obj.parent().parent().find(".password").val(),
                "allowed_conn": JSON.stringify(allowed_conn)
            },
            success: function(res){
                if(res == "200"){
                    this_obj.addClass("hidden");
                    this_obj.next().removeClass("hidden");
                    this_obj.next().next().addClass("hidden");
                    this_obj.parent().parent().find(".td-input").prop("disabled", true);
                }
            }
        });
    });

    $(".edit-btn").on("click", function(){
        var this_obj = $(this);
        this_obj.addClass("hidden");
        this_obj.prev().removeClass("hidden");
        this_obj.next().removeClass("hidden");
        this_obj.parent().parent().find(".td-input").prop("disabled", false);
    });

    $(".cancel-btn").on("click", function(){
        var this_obj = $(this);
        this_obj.addClass("hidden");
        this_obj.prev().removeClass("hidden");
        this_obj.prev().prev().addClass("hidden");
        this_obj.parent().parent().find(".td-input").prop("disabled", true);
    });

    $(".delete-btn").on("click", function(){
        var this_obj = $(this);
        var id = this_obj.parent().parent().find(".id").html();

        $.ajax({
            type: "POST",
            url: "/delete_guest",
            data: {
                "id": id
            },
            success: function(res){
                if(res == "200"){
                    this_obj.parent().parent().remove();
                    $(`input.${id}`).parent().parent().remove();
                }
            }
        });
    });
});

function openForm(){
    $("#pop-up-window").removeClass("hidden");
}

function closeForm(){
    $("#pop-up-window").addClass("hidden");
}

function submitForm(){
    var new_allowed_conn = ""
    $("#new-allowed-conn-list").find("input").each((i, input) => {
        if($(input).prop("checked") == true){
            new_allowed_conn += `${$(input).attr("class")},`;
        }
    });
    $("#new-allowed-conn").val(new_allowed_conn.slice(0, -1));
    $("#new-guest-form").submit();
}
