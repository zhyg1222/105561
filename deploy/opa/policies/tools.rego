package xiaojuju.authz

default decision := {"effect": "deny", "reason": "default_deny"}

decision := {"effect": "allow", "reason": "public_read"} if {
    input.tool == "web.search"
}

decision := {"effect": "allow", "reason": "owner_message"} if {
    input.tool == "message.send"
    input.contact_id == "owner"
    input.shadow == false
}
decision := {"effect": "require_approval", "reason": "public_publish"} if {
    input.tool == "browser.publish"
}

decision := {"effect": "deny", "reason": "shadow_side_effect"} if {
    input.shadow == true
    startswith(input.tool, "message.")
}