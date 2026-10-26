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