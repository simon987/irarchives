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

window.onload = function () {
    M.Tabs.init(document.getElementById("rri_menu"), {});
    get_subreddits();
    get_status();
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
    const results_el = gebi('output');
    const pl = mkPreloader();
    results_el.appendChild(pl);

    const q = gebi("search").value;

    const request = new XMLHttpRequest();
    request.open("GET", 'search?q=' + q, true);
    request.send(null);
    request.onreadystatechange = function () {
        if (request.readyState === 4) {
            if (request.status === 200) {
                pl.remove();
                handleSearchResponse(request.responseText)
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
        results_el.appendChild(mkHeader(`Error: ${resp['error']}`));
        return;
    }

    if (!resp.posts.length && !resp.comments.length && !resp.related.length) {
        results_el.appendChild(mkHeader(`No results`));
        return;
    }

    if (resp['images']) {
        results_el.appendChild(mkGallery(resp['images']));
    }

    // POSTS
    if (resp.posts && resp.posts.length > 0) {
        results_el.appendChild(mkHeader(`${resp.posts.length} post${resp.comments.length === 1 ? '' : 's'}`));
        for (let i in resp['posts']) {
            results_el.appendChild(mkPost(resp['posts'][i]));
        }
    }

    // COMMENTS
    if (resp.comments && resp.comments.length > 0) {
        results_el.appendChild(mkHeader(`${resp.comments.length} comment${resp.comments.length === 1 ? '' : 's'}`));
        for (let i in resp['comments']) {
            results_el.appendChild(mkComment(resp['comments'][i]));
        }
    }

    // RELATED COMMENTS
    if (resp.related && resp.related.length > 0) {
        results_el.appendChild(mkHeader(`${resp.related.length} related comment${resp.comments.length === 1 ? '' : 's'}`));
        for (let i in resp['related']) {
            results_el.appendChild(mkComment(resp['related'][i]));
        }
    }
}

function get_time(seconds) {
    let diff = Math.round(new Date().getTime() / 1000) - seconds;
    const d = {
        'second': 60,
        'minute': 60,
        'hour': 24,
        'day': 30,
        'month': 12,
        'year': 1000
    };
    for (let key in d) {
        if (diff <= d[key]) {
            diff = diff.toFixed(0);
            let result = diff + ' ';
            result += key;
            if (diff !== "1")
                result += 's';
            result += ' ago';
            return result;
        }
        diff /= d[key];
    }
    return '? days ago';
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

function mkHeader(text) {
    const el = document.createElement('h5');
    el.setAttribute('class', 'white-text');
    el.appendChild(document.createTextNode(text));
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

    const cardImageWrapper = document.createElement('div');
    cardImageWrapper.setAttribute('class', 'card-image img_wrapper');

    const cardImage = document.createElement('img');
    cardImage.setAttribute('src', post.thumb);

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
    info.appendChild(mkBold(get_time(post.created), new Date(post.created * 1000).toUTCString()));
    info.appendChild(document.createTextNode(' by '));
    info.appendChild(mkCallback(function () {
        research("user:" + post.author)
    }, post.author, 'Search this user'));
    info.appendChild(document.createTextNode(' to '));
    info.appendChild(mkLink('http://www.reddit.com/r/' + post.subreddit, post.subreddit));
    right.appendChild(info);

    right.appendChild(mkLink('http://www.reddit.com/' + post.permalink,
        (post.comments === 1 ? "1 comment" : `${post.comments} comments`)
    ));
    if (post.width !== 0 && post.height !== 0) {
        right.appendChild(document.createTextNode(' '));
        right.appendChild(mkLink(post.imageurl,
            `  (⛶ ${post.width}x${post.height} ${bytes_to_readable(post.size)})`
        ));
    }

    card.appendChild(cardImageWrapper);
    card.appendChild(cardStacked);
    card.appendChild(mkExtSearchLinks(post.imageurl));
    cardImageWrapper.appendChild(cardImage);
    cardStacked.appendChild(cardContent);
    cardContent.appendChild(contentWrapper);
    contentWrapper.appendChild(left);
    contentWrapper.appendChild(right);
    contentWrapper.appendChild(mkExtSearchLinksMobile(post.imageurl));

    return card;
}

function mkComment(comment) {

    const card = document.createElement('div');
    card.setAttribute('class', 'card comment');
    const cardContent = document.createElement('div');
    cardContent.setAttribute('class', 'card-content');

    const contentWrapper = document.createElement('div');
    contentWrapper.setAttribute('class', 'row');

    const right = document.createElement('div');
    right.setAttribute('class', 'col s10 m10 l11');

    const left = document.createElement('div');
    left.setAttribute('class', 'col s2 m2 l1');
    left.appendChild(mkUpboat(comment.ups - comment.downs));

    const info = document.createElement('p');
    info.appendChild(document.createTextNode('Commented '));
    info.appendChild(mkBold(get_time(comment.created), new Date(comment.created * 1000).toUTCString()));
    info.appendChild(document.createTextNode(' by '));
    info.appendChild(mkCallback(function () {
        research("user:" + comment.author)
    }, comment.author, 'Search this user'));
    info.appendChild(mmd(comment.body, comment.url === null ? comment.imageurl : comment.url));
    right.appendChild(info);

    const actions = document.createElement('div');
    actions.setAttribute('class', 'card-action');
    actions.appendChild(mkLink(`http://reddit.com/comments/${comment.postid}/_/${comment.hexid}`, "permalink"));

    if (comment.width !== 0 && comment.height !== 0 && comment.size !== 0) {
        actions.appendChild(mkLink(comment.imageurl,
            `⛶ ${comment.width}x${comment.height} ${bytes_to_readable(comment.size)}`
        ));
    }

    card.appendChild(cardContent);
    cardContent.appendChild(contentWrapper);
    contentWrapper.appendChild(left);
    contentWrapper.appendChild(right);
    card.appendChild(actions);
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

function mkCallback(callback, text, title = '') {
    const el = document.createElement('button');
    el.addEventListener('click', callback);
    el.setAttribute('class', 'btn-flat callback_btn');
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
    for (let i = 0; i < rows; i++) {
        let col = document.createElement('div');
        col.setAttribute('class', `col s${12 / rows}`);
        gallery.appendChild(col);
        cols.push(col);
    }

    let col = 0;
    for (let i in images) {
        if (col === rows) {
            col = 0;
        }
        const img = document.createElement('img');
        img.setAttribute('src', images[i].thumb);
        cols[col].appendChild(img);
        col++;
    }

    return gallery;
}
