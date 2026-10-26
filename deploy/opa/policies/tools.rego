package xiaojuju.authz

default decision := {"effect": "deny", "reason": "default_deny"}

decision := {"effect": "deny", "reason": "shadow_side_effect"} if {
    input.shadow == true
    input.side_effect == true
}

decision := {"effect": "allow", "reason": "public_read"} if {
    input.tool == "web.search"
    input.side_effect == false
}

decision := {"effect": "allow", "reason": "owner_message"} if {
    input.tool == "message.send"
    input.contact_id == "owner"
    input.shadow == false
    input.side_effect == true
}

decision := {"effect": "require_approval", "reason": "public_publish"} if {
    input.tool == "browser.publish"
    input.shadow == false
    input.side_effect == true
}
