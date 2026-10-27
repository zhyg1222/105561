package xiaojuju.authz

test_shadow_side_effect_denied if {
    decision := data.xiaojuju.authz.decision with input as {
        "tool": "browser.publish",
        "contact_id": "owner",
        "shadow": true,
        "side_effect": true,
    }
    decision.effect == "deny"
    decision.reason == "shadow_side_effect"
}

test_unavailable_or_unknown_tool_defaults_deny if {
    decision := data.xiaojuju.authz.decision with input as {
        "tool": "payment.send",
        "contact_id": "owner",
        "shadow": false,
        "side_effect": true,
    }
    decision.effect == "deny"
}

test_owner_message_allowed if {
    decision := data.xiaojuju.authz.decision with input as {
        "tool": "message.send",
        "contact_id": "owner",
        "shadow": false,
        "side_effect": true,
    }
    decision.effect == "allow"
}

test_public_publish_requires_approval if {
    decision := data.xiaojuju.authz.decision with input as {
        "tool": "browser.publish",
        "contact_id": "owner",
        "shadow": false,
        "side_effect": true,
    }
    decision.effect == "require_approval"
}


test_social_publish_requires_approval if {
    decision := data.xiaojuju.authz.decision with input as {
        "tool": "social.publish",
        "contact_id": "owner",
        "shadow": false,
        "side_effect": true,
    }
    decision.effect == "require_approval"
}


test_external_message_requires_approval if {
    decision := data.xiaojuju.authz.decision with input as {
        "tool": "message.send",
        "contact_id": "friend",
        "shadow": false,
        "side_effect": true,
    }
    decision.effect == "require_approval"
    decision.reason == "external_message"
}
