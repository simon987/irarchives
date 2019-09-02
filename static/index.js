let helpModal;

//Markdown to html https://github.com/p01/mmd.js
function mmd(s) {
    let h = '';

    function E(s) {
        return new Option(s).innerHTML
    }

    function I(s) {
        return E(s).replace(/!\[([^\]]*)]\(([^(]+)\)/g, '<img alt="$1"src="$2">').replace(/\[([^\]]+)]\(([^(]+)\)/g, '$1'.link('$2')).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/\*([^*]+)\*/g, '<em>$1</em>')
    }

    s.replace(/^\s+|\r|\s+$/g, '').replace(/\t/g, ' ').split(/\n\n+/).forEach(function (b, f, R) {
        R = {
            '*': [/\n\* /, '<ul><li>', '</li></ul>'],
            1: [/\n[1-9]\d*\.? /, '<ol><li>', '</li></ol>'],
            ' ': [/\n /, '<pre><code>', '</pre></code>', '\n'],
            '>': [/\n> /, '<blockquote>', '</blockquote>', '\n']
        }[f = b[0]];
        h += R ? R[1] + ('\n' + b).split(R[0]).slice(1).map(R[3] ? E : I).join(R[3] || '</li>\n<li>') + R[2] : f === '#' ? '<h' + (f = b.indexOf(' ')) + '>' + I(b.slice(f + 1)) + '</h' + f + '>' : f === '<' ? b : '<p>' + I(b) + '</p>'
    });
    let p = document.createElement('p');
    p.innerHTML = h;
    return p
}

function getImageBlob(event) {
    const items = (event.clipboardData || event.originalEvent.clipboardData).items;
    for (let i in items) {
        const item = items[i];
        if (item.kind === 'file') {
            return item.getAsFile();
        }
    }
}

function uploadBlob(blob) {
    const reader = new FileReader();
    reader.onload = function (event) {

        clearResults();
        const results_el = gebi('output');
        const pl = mkPreloader();
        results_el.appendChild(pl);

        const form = new FormData();
        form.append('fname', 'image');
        form.append('data', event.target.result);

        const request = new XMLHttpRequest();
        request.open("POST", 'upload', true);
        request.send(form);
        request.onreadystatechange = function () {
            if (request.readyState === 4) {
                if (request.status === 200) {
                    const json = JSON.parse(request.responseText);
                    gebi("search").value = json.url;
                    handleSearchResponse(request.responseText);
                    pl.remove();
                } else {
                    console.log(request.responseText)
                }
            }
        };
    };
    reader.readAsDataURL(blob);
}


window.onload = function () {
    M.Modal.init(document.querySelectorAll(".modal"), {});
    M.Tabs.init(document.getElementById("rri_menu"), {});
    M.Tabs.init(document.getElementById("search-menu"), {});
    helpModal = M.Modal.getInstance(document.getElementById("help"));
    get_subreddits();
    get_status();
    gebi("search").addEventListener("paste", function (e) {
        const blob = getImageBlob(e);
        if (blob) {
            uploadBlob(blob)
        }
    }, false);
};


function gebi(id) {
    return document.getElementById(id);
}

function get_subreddits() {
    const request = new XMLHttpRequest();
    request.open("GET", 'subreddits', true);
    request.send(null);
    request.onreadystatechange = function () {
        if (request.readyState === 4) {
            if (request.status === 200) {
                gebi('subreddit_err').classList.remove("active");

                const json = JSON.parse(request.responseText);

                if (json['error'] != null) {
                    gebi('subreddits').innerText = 'error: ' + json["error"];
                    return;
                }

                const subreddits = json['subreddits'];
                let output = '<div id="subreddit_header">Monitoring ' + subreddits.length + ' subreddits</div>';
                for (let i in subreddits) {
                    output += '<span class="subreddit">' +
                        '<a class="subreddit" href="http://www.reddit.com/r/' +
                        subreddits[i] + '" target="_new">' + subreddits[i] + '</a></span> ';
                }
                gebi('subreddits').innerHTML = output;

            } else {
                gebi('subreddit_err').innerText = "Error: " + request.status;
                gebi('subreddit_err').classList.add("active")
            }
        }
    }
}

// Add commas to the thousands places in a number
function number_commas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function get_status() {
    const request = new XMLHttpRequest();
    request.open("GET", 'status', true);
    request.send(null);
    request.onreadystatechange = function () {
        if (request.readyState === 4) {
            if (request.status === 200) {
                const resp = JSON.parse(request.responseText)["status"];
                gebi("db_images").innerText = number_commas(resp['images']);
                gebi("db_posts").innerText = number_commas(resp['posts']);
                gebi("db_videos").innerText = number_commas(resp['videos']);
                gebi("db_comments").innerText = number_commas(resp['comments']);
                gebi("db_albums").innerText = number_commas(resp['albums']);
                gebi("db_subreddits").innerText = number_commas(resp['subreddits']);
            }
        }
    }
}

function research(q) {
    gebi("search").value = q;
    query();
}

function clearResults() {
    const results_el = gebi('output');
    while (results_el.hasChildNodes()) {
        results_el.removeChild(results_el.lastChild);
    }
}

function query() {
    clearResults();

    const q = gebi("search").value;
    let params = {};

    q.split(/\s+/).forEach(tok => {
        params[tok.match(/^(?!https?)(\w+):/) ? tok.match(/^(?!https?)^(\w+):/)[1] : "image"]
            = tok.substring(tok.match(/^(?!https?)(\w+):/) ? tok.match(/^\w+:/)[0].length : 0)
    })

    params["d"] = params["d"] || 0
    let queryString = "search?d=" + params["d"]

    if (params["image"]) {
        queryString += '&img=' + params["image"]
    }
    if (params["frames"]) {
        queryString += '&f=' + params["frames"]
    }
    if (params["video"]) {
        queryString += '&vid=' + params["video"]
    }
    if (params["album"]) {
        queryString += '&album=' + params["album"]
    }
    if (params["user"]) {
        queryString += '&user=' + params["user"]
    }

    //TODO: sha1 etc

    const results_el = gebi('output');
    const pl = mkPreloader();
    results_el.appendChild(pl);

    const request = new XMLHttpRequest();
    request.open("GET", queryString, true);
    request.send(null);
    request.onreadystatechange = function () {
        if (request.readyState === 4) {
            if (request.status === 200) {
                pl.remove();
                handleSearchResponse(request.responseText)
            } else if (request.status === 504) {
                results_el.appendChild(mkErrorMsg(`Query timed out, try again in a few minutes.`));
            }
        }
    };

    // Don't refresh page on submit
    return false;
}

function handleSearchResponse(responseText) {

    const results_el = gebi('output');
    const resp = JSON.parse(responseText);

    if (resp['error'] != null) {
        results_el.appendChild(mkErrorMsg(`Error: ${resp['error']}`));
        return;
    }

    //TODO: no!
    if (resp['images']) {
        results_el.appendChild(mkGallery(resp['images']));
        return
    }

    if (resp.result_count === 0) {
        results_el.appendChild(mkErrorMsg('No results'));
        return;
    }

    results_el.appendChild(mkHeader(`${resp.result_count} item${resp.result_count === 1 ? '' : 's'}`));
    for (let i in resp['hits']) {
        if (resp['hits'][i]['type'] === 'comment') {
            results_el.appendChild(mkComment(resp['hits'][i]));
        } else {
            results_el.appendChild(mkPost(resp['hits'][i]));
        }
    }
}

function get_time(seconds) {
    const d = {
        'second': 60,
        'minute': 60,
        'hour': 24,
        'day': 30,
        'month': 12,
        'year': 1000
    };
    for (let key in d) {
        if (seconds <= d[key]) {
            seconds = seconds.toFixed(0);
            let result = seconds + ' ';
            result += key;
            if (seconds !== "1")
                result += 's';
            return result;
        }
        seconds /= d[key];
    }
    return '?';
}

function get_time_diff(seconds) {
    return get_time(Math.round(new Date().getTime() / 1000) - seconds);
}

function bytes_to_readable(bytes) {
    const scale = ['B', 'KB', 'MB'];
    for (let i = scale.length - 1; i >= 0; i--) {
        const cur = Math.pow(1024, i);
        if (cur < bytes) {
            return (bytes / cur).toFixed(1) + scale[i];
        }
    }
    return '?bytes';
}

function get_video_thumbs(videoId, cb) {

    const request = new XMLHttpRequest();
    request.open("GET", "/video_thumbs/" + videoId, true);
    request.send(null);
    request.onreadystatechange = function () {
        if (request.readyState === 4) {
            if (request.status === 200) {
                cb(
                    JSON.parse(request.responseText)["thumbs"]
                        .map(t => t.toString())
                        .map(tn => {
                            return "/static/thumbs/vid/" + tn[0]
                                + "/" + (tn.length > 1 ? tn[1] : "0")
                                + "/" + tn + ".jpg";
                        })
                )
            }
        }
    };
}

function bits_to_readable(bytes) {
    const scale = ['b', 'Kb', 'Mb'];
    for (let i = scale.length - 1; i >= 0; i--) {
        const cur = Math.pow(1024, i);
        if (cur < bytes) {
            return (bytes / cur).toFixed(1) + scale[i];
        }
    }
    return '?bits';
}

function mkHeader(text) {
    const el = document.createElement('h5');
    el.setAttribute('class', 'white-text');
    el.appendChild(document.createTextNode(text));
    return el;
}

function mkErrorMsg(text) {
    const el = document.createElement('h5');
    el.setAttribute('class', 'white-text');
    el.appendChild(document.createTextNode(text));

    const helpLink = document.createElement("a")
    helpLink.setAttribute("class", "modal-trigger help-link")
    helpLink.setAttribute("href", "#help")
    helpLink.appendChild(document.createTextNode("(Help!)"))
    el.appendChild(helpLink);

    return el;
}

function mkExtSearchLinks(url) {
    const el = document.createElement('div');
    el.setAttribute('class', 'card-action');
    el.appendChild(mkLink(`https://images.google.com/searchbyimage?image_url=${url}`, 'Google'));
    el.appendChild(mkLink(`https://www.tineye.com/search?pluginver=bookmark_1.0&url=${url}`, 'TinEye'));
    el.appendChild(mkLink(`https://www.karmadecay.com/${url.replace('http:', '').replace('https:', '')}`, 'KarmaDecay'));
    return el;
}

function mkExtSearchLinksMobile(url) {
    const el = document.createElement('div');
    el.setAttribute('class', 'reverse_links');
    el.appendChild(mkButton(`https://images.google.com/searchbyimage?image_url=${url}`, 'Google'));
    el.appendChild(mkButton(`https://www.tineye.com/search?pluginver=bookmark_1.0&url=${url}`, 'TinEye'));
    el.appendChild(mkButton(`https://www.karmadecay.com/${url.replace('http:', '').replace('https:', '')}`, 'KarmaDecay'));
    return el;
}

function mkPost(post) {

    const card = document.createElement('div');
    card.setAttribute('class', 'card horizontal post');
    const cardStacked = document.createElement('div');
    cardStacked.setAttribute('class', 'card-stacked');
    const cardContent = document.createElement('div');
    cardContent.setAttribute('class', 'card-content');
    const cardTitle = document.createElement('span');
    cardTitle.setAttribute('class', 'card-title');
    cardTitle.appendChild(document.createTextNode(post.title));
    cardContent.appendChild(cardTitle);

    const cardItemWrapper = document.createElement('div');
    cardItemWrapper.setAttribute('class', 'card-image img_wrapper');

    let cardItem;
    if (post.item.type === 'image') {
        cardItem = document.createElement('img');
        cardItem.setAttribute('src', post.item.thumb);
    } else {
        cardItem = makeSlideShow(post.item.video_id, post.item.duration);
    }

    const contentWrapper = document.createElement('div');
    contentWrapper.setAttribute('class', 'row');

    const right = document.createElement('div');
    right.setAttribute('class', 'col s10 l11');

    const left = document.createElement('div');
    left.setAttribute('class', 'col s2 l1');
    left.setAttribute('style', 'padding: 0');
    left.appendChild(mkUpboat(post.ups - post.downs));

    const info = document.createElement('p');
    info.appendChild(document.createTextNode('Submitted '));
    info.appendChild(mkBold(get_time_diff(post.created), new Date(post.created * 1000).toUTCString()));
    info.appendChild(document.createTextNode(' ago by '));
    if (post.author.toLowerCase() !== "[deleted]") {
        info.appendChild(mkCallback(function () {
            research("user:" + post.author)
        }, post.author, 'Search this user'));
    } else {
        info.appendChild(document.createTextNode(post.author));
    }
    info.appendChild(document.createTextNode(' to '));
    info.appendChild(mkLink('http://www.reddit.com/r/' + post.subreddit, post.subreddit));
    right.appendChild(info);

    right.appendChild(mkLink('http://www.reddit.com/' + post.permalink,
        (post.comments === 1 ? "1 comment" : `${post.comments} comments`)
    ));

    right.appendChild(document.createTextNode(' '));
    right.appendChild(mkLink(post.item.url,
        post.item.type === 'image'
            ? `  (⛶ ${post.item.width}x${post.item.height} ${bytes_to_readable(post.item.size)})`
            : `  (▷ ${post.item.height}p ${bits_to_readable(post.item.bitrate)}/s ${get_time(post.item.duration)} ${bytes_to_readable(post.item.size)})`
    ));


    card.appendChild(cardItemWrapper);
    card.appendChild(cardStacked);

    cardItemWrapper.appendChild(cardItem);
    cardStacked.appendChild(cardContent);
    cardContent.appendChild(contentWrapper);
    contentWrapper.appendChild(left);
    contentWrapper.appendChild(right);

    let links = mkExtSearchLinks(post.item.url);
    let mobileLinks = mkExtSearchLinksMobile(post.item.url);

    if (post.item.album_url !== null) {
        links.appendChild(mkCallback(
            () => research("album:" + post.item.album_url),
            "album", post.item.album_url,
        ));
        mobileLinks.appendChild(mkCallback(
            () => research("album:" + post.item.album_url),
            "album", post.item.album_url,
            true
        ));
    }

    card.appendChild(links);
    contentWrapper.appendChild(mobileLinks);

    return card;
}

function mkComment(comment) {

    const card = document.createElement('div');
    card.setAttribute('class', 'card horizontal comment');
    const cardContent = document.createElement('div');
    cardContent.setAttribute('class', 'card-content');

    const cardItemWrapper = document.createElement('div');
    cardItemWrapper.setAttribute('class', 'card-image img_wrapper');

    let cardItem;
    if (comment.item.type === 'image') {
        cardItem = document.createElement('img');
        cardItem.setAttribute('src', comment.item.thumb);
    } else {
        cardItem = makeSlideShow(comment.item.video_id, comment.item.duration);
    }

    const contentWrapper = document.createElement('div');
    contentWrapper.setAttribute('class', 'row');

    const right = document.createElement('div');
    right.setAttribute('class', 'col s10 m10 l11');

    const left = document.createElement('div');
    left.setAttribute('class', 'col s2 m2 l1');
    left.appendChild(mkUpboat(comment.ups - comment.downs));

    const info = document.createElement('p');
    info.appendChild(document.createTextNode('Commented '));
    info.appendChild(mkBold(get_time_diff(comment.created), new Date(comment.created * 1000).toUTCString()));
    info.appendChild(document.createTextNode(' ago by '));
    if (comment.author.toLowerCase() !== "[deleted]") {
        info.appendChild(mkCallback(function () {
            research("user:" + comment.author)
        }, comment.author, 'Search this user'));
    } else {
        info.appendChild(document.createTextNode(comment.author));
    }
    info.appendChild(mmd(comment.body));
    right.appendChild(info);

    if (comment.item) {
        right.appendChild(mkLink(comment.item.url,
            comment.item.type === 'image'
                ? `  (⛶ ${comment.item.width}x${comment.item.height} ${bytes_to_readable(comment.item.size)})`
                : `  (▷ ${comment.item.height}p ${bits_to_readable(comment.item.bitrate)}/s ${get_time(comment.item.duration)} ${bytes_to_readable(comment.item.size)})`
        ));
    }

    card.appendChild(cardItemWrapper);
    card.appendChild(cardContent);
    cardContent.appendChild(contentWrapper);
    cardItemWrapper.appendChild(cardItem);
    contentWrapper.appendChild(left);
    contentWrapper.appendChild(right);

    let links = mkExtSearchLinks(comment.item.url);
    let mobileLinks = mkExtSearchLinksMobile(comment.item.url);

    if (comment.item.album_url !== null) {
        links.appendChild(mkCallback(
            () => research("album:" + comment.item.album_url),
            "album", comment.item.album_url,
        ));
        mobileLinks.appendChild(mkCallback(
            () => research("album:" + comment.item.album_url),
            "album", comment.item.album_url,
            true
        ));
    }
    card.appendChild(links);
    contentWrapper.appendChild(mobileLinks);

    return card;
}

function mkBold(text, title = "") {
    const el = document.createElement('span');
    el.setAttribute('class', 'bold');
    el.setAttribute('title', title);
    el.appendChild(document.createTextNode(text));
    return el
}

function mkLink(href, text, target = "_blank") {
    const el = document.createElement('a');
    el.setAttribute('href', href);
    el.setAttribute('target', target);
    el.appendChild(document.createTextNode(text));
    return el
}

function mkButton(href, text, target = "_blank") {
    const el = document.createElement('a');
    el.setAttribute('href', href);
    el.setAttribute('class', 'waves-effect waves-light btn');
    el.setAttribute('target', target);
    el.appendChild(document.createTextNode(text));
    return el
}

function mkCallback(callback, text, title = '', button) {
    const el = document.createElement("a");
    el.addEventListener('click', callback);
    if (button) {
        el.setAttribute('class', 'callback_btn waves-effect waves-light btn');
    } else {
        el.setAttribute('class', 'callback_btn');
    }
    el.setAttribute('title', title);
    el.appendChild(document.createTextNode(text));
    return el
}

function mkPreloader() {
    const el = document.createElement('div');
    el.setAttribute('class', 'progress');
    const indeterminate = document.createElement('div');
    indeterminate.setAttribute('class', 'indeterminate');
    el.appendChild(indeterminate);
    return el;
}

function mkUpboat(count) {
    const el = document.createElement('div');
    el.setAttribute('class', 'upboat');
    const up = document.createElement('span');
    up.setAttribute('class', 'up');
    up.appendChild(document.createTextNode('▲'));
    const votes = document.createElement('span');
    votes.setAttribute('class', 'votes');
    votes.appendChild(document.createTextNode(count));
    const down = document.createElement('span');
    down.setAttribute('class', 'down');
    down.appendChild(document.createTextNode('▼'));
    el.appendChild(up);
    el.appendChild(votes);
    el.appendChild(down);
    return el;
}

//TODO: set rows based on screen width
function mkGallery(images, rows = 3) {
    const gallery = document.createElement('div');
    gallery.setAttribute('class', 'row');

    let cols = [];
    let colHeights = [];
    for (let i = 0; i < rows; i++) {
        let col = document.createElement('div');
        col.setAttribute('class', `col s${12 / rows}`);
        gallery.appendChild(col);
        cols.push(col);
        colHeights.push(0);
    }

    for (let im in images) {

        let minHeight = Number.MAX_VALUE;
        let min = 0;

        for (let i = 0; i < cols.length; i++) {
            if (colHeights[i] < minHeight) {
                minHeight = colHeights[i];
                min = i;
            }
        }

        const img = document.createElement('img');
        img.setAttribute('src', images[im].thumb);
        cols[min].appendChild(img);
        colHeights[min] += height(images[im]);
    }

    return gallery;
}

// Quick hack to estimate img height in a col
function height(im) {

    const TNSIZE = 404.167;

    if (im.width > im.height) {
        return TNSIZE * (im.width / im.height)
    } else {
        return TNSIZE * (im.height / im.width)
    }
}

function makeSlideShow(videoId, duration) {

    const el = document.createElement('div');
    el.setAttribute("class", "slideshow");

    get_video_thumbs(videoId, function (images) {

        for (let i = 0; i < images.length; i++) {
            const img = document.createElement("img");
            if (i === 0) {
                img.setAttribute("class", "gallery-item showcase-img");
            } else {
                img.setAttribute("class", "gallery-item");
            }
            img.setAttribute("src", images[i]);
            el.appendChild(img);
        }

        let imageCounter = images.length;
        let timer = undefined

        el.onmouseenter = function () {
            timer = window.setInterval(function () {
                const images = el.querySelectorAll(".gallery-item");
                let newIndex = imageCounter % images.length;
                let lastIndex = 0;
                newIndex === 0 ? lastIndex = images.length - 1 : lastIndex = newIndex - 1;
                images[newIndex].classList.add("showcase-img");
                images[lastIndex].classList.remove("showcase-img");

                imageCounter += 1;
            }, duration / images.length * 800)
        }

        el.onmouseleave = function () {
            if (timer) {
                window.clearInterval(timer)
                timer = undefined
            }
        }
    })

    return el;
}
