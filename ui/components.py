import streamlit as st


def render_flight_cards(data: dict) -> None:
    flights = data.get("best_flights", [])
    if not flights:
        st.caption("No flights found for these criteria.")
        return

    st.markdown("**✈ Flights**")
    for f in flights:
        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                logo = f.get("airline_logo", "")
                if logo and logo.startswith("http"):
                    try:
                        st.image(logo, width=60)
                    except Exception:
                        pass
                st.caption(f.get("airline", ""))
            with col2:
                dep = f.get("departure_time", "")
                arr = f.get("arrival_time", "")
                st.markdown(f"**{dep}** → **{arr}**")
                stops = f.get("stops", 0)
                stop_label = "Nonstop" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
                mins = f.get("duration_minutes", 0)
                h, m = divmod(mins, 60)
                st.caption(f"{stop_label} · {h}h {m}m")
            with col3:
                price = f.get("price", 0)
                currency = f.get("currency", "USD")
                st.metric("", f"${price}" if currency == "USD" else f"{price} {currency}")
                link = f.get("booking_token", "")
                if link:
                    st.link_button("Book", link)


def render_hotel_cards(data: dict) -> None:
    hotels = data.get("hotels", [])
    if not hotels:
        st.caption("No hotels found for these criteria.")
        return

    st.markdown("**🏨 Hotels**")
    for h in hotels:
        with st.container(border=True):
            col1, col2 = st.columns([1, 2])
            with col1:
                if h.get("image_url"):
                    st.image(h["image_url"], use_container_width=True)
            with col2:
                st.subheader(h.get("name", ""))
                rating = h.get("rating", 0)
                reviews = h.get("reviews", 0)
                filled = round(rating / 2)
                stars = "★" * filled + "☆" * (5 - filled)
                st.markdown(f"{stars} **{rating}/10** · {reviews:,} reviews")
                ppn = h.get("price_per_night", 0)
                total = h.get("total_price", 0)
                if ppn:
                    st.markdown(f"**${ppn:.0f}/night**" + (f" · ${total:.0f} total" if total else ""))
                amenities = h.get("amenities", [])[:5]
                if amenities:
                    st.caption(" · ".join(amenities))
                link = h.get("booking_link", "")
                if link:
                    st.link_button("View Hotel", link)


def render_restaurant_cards(data: dict) -> None:
    restaurants = data.get("restaurants", [])
    if not restaurants:
        st.caption("No restaurants found for these criteria.")
        return

    st.markdown("**🍽 Restaurants**")
    cols = st.columns(min(len(restaurants), 3))
    for i, r in enumerate(restaurants[:6]):
        with cols[i % 3]:
            with st.container(border=True):
                if r.get("image_url"):
                    st.image(r["image_url"], use_container_width=True)
                st.markdown(f"**{r.get('name', '')}** {r.get('price_level', '')}")
                st.caption(f"{r.get('cuisine', '')} · ★ {r.get('rating', 'N/A')} ({r.get('reviews', 0):,})")
                st.caption(r.get("address", ""))
                if r.get("hours"):
                    st.caption(f"⏰ {r['hours']}")
                link = r.get("maps_link", "") or r.get("website", "")
                if link:
                    st.link_button("Maps", link)


def render_weather_card(data: dict) -> None:
    if data.get("error"):
        st.warning(f"Weather: {data['error']}")
        return

    city = data.get("city", "")
    country = data.get("country", "")
    forecast = data.get("forecast", [])

    st.markdown(f"**🌤 Weather in {city}{', ' + country if country else ''}**")

    if data.get("note"):
        st.info(data["note"])

    if forecast:
        cols = st.columns(min(len(forecast), 5))
        for i, day in enumerate(forecast[:5]):
            with cols[i]:
                if day.get("icon_url"):
                    st.image(day["icon_url"], width=50)
                st.caption(day["date"])
                st.markdown(f"**{day['temp_high_f']}°F**")
                st.caption(f"{day['temp_low_f']}°F")
                st.caption(day.get("description", "").title())

    tips = data.get("packing_tips", [])
    if tips:
        with st.expander("Packing Tips"):
            for tip in tips:
                st.markdown(f"- {tip}")


def render_distance_card(data: dict) -> None:
    if data.get("error"):
        st.warning(f"Distance: {data['error']}")
        return
    summary = data.get("summary", "")
    if summary:
        st.info(f"📍 {summary}")


def render_transport_card(data: dict) -> None:
    routes = data.get("routes", [])
    if not routes:
        st.caption("No transport options found.")
        return

    st.markdown("**🚇 Local Transport Options**")
    type_icons = {"metro": "🚇", "bus": "🚌", "taxi": "🚕", "rideshare": "🚗", "walking": "🚶", "train": "🚆"}

    for r in routes:
        icon = type_icons.get(r.get("type", ""), "🚌")
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"{icon} **{r.get('provider', r.get('type', ''))}**")
                st.caption(r.get("description", ""))
            with col2:
                st.metric("Cost", r.get("cost_estimate", "—"))
                st.caption(f"{r.get('duration_minutes', '?')} min")
            link = r.get("booking_link")
            if link:
                st.link_button("Book", link)


def render_intercity_cards(data: dict) -> None:
    options = data.get("options", [])
    if not options:
        st.caption("No travel options found.")
        return

    origin = data.get("origin", "")
    destination = data.get("destination", "")
    st.markdown(f"**🗺 Travel Options: {origin} → {destination}**")

    type_icons = {"driving": "🚗", "bus": "🚌", "train": "🚆"}

    for opt in options:
        icon = type_icons.get(opt.get("type", ""), "🚌")
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"{icon} **{opt.get('provider', '')}**")
                st.caption(opt.get("description", ""))
                if opt.get("distance_miles"):
                    st.caption(f"📏 {opt['distance_miles']} miles ({opt.get('distance_km', '')} km)")
            with col2:
                st.metric("Cost", opt.get("cost_estimate", "—"))
                dur = opt.get("duration_minutes")
                if dur:
                    h, m = divmod(dur, 60)
                    st.caption(f"⏱ {h}h {m}min" if h else f"⏱ {m}min")
            link = opt.get("booking_link")
            if link:
                st.link_button("View Route / Book", link)


def render_attraction_cards(data: dict) -> None:
    attractions = data.get("attractions", [])
    if not attractions:
        st.caption("No attractions found.")
        return

    destination = data.get("destination", "")
    st.markdown(f"**🗺 Things to Do in {destination}**")

    cols = st.columns(min(len(attractions), 3))
    for i, a in enumerate(attractions[:9]):
        with cols[i % 3]:
            with st.container(border=True):
                if a.get("image_url"):
                    st.image(a["image_url"], use_container_width=True)
                st.markdown(f"**{a.get('name', '')}**")
                st.caption(a.get("type", ""))
                rating = a.get("rating")
                reviews = a.get("reviews")
                if rating:
                    reviews_str = f" ({reviews:,})" if reviews else ""
                    st.caption(f"★ {rating}{reviews_str}")
                price = a.get("price", "")
                if price:
                    st.caption(f"💰 {price}")
                if a.get("hours"):
                    st.caption(f"⏰ {a['hours']}")
                desc = a.get("description", "")
                if desc:
                    st.caption(desc[:120] + ("..." if len(desc) > 120 else ""))
                link = a.get("maps_link") or a.get("website", "")
                if link:
                    st.link_button("View", link)


def render_tool_results_in_chat(tool_name: str, result: dict) -> None:
    renderers = {
        "search_flights": render_flight_cards,
        "search_hotels": render_hotel_cards,
        "search_restaurants": render_restaurant_cards,
        "get_weather": render_weather_card,
        "get_distance": render_distance_card,
        "get_local_transport": render_transport_card,
        "search_intercity_travel": render_intercity_cards,
        "search_attractions": render_attraction_cards,
    }
    renderer = renderers.get(tool_name)
    if renderer:
        renderer(result)
