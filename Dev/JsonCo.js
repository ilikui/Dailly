
fetch('https://www.buzzing.cc/feed.json')
  .then(response => response.json())
  .then(data => {
    // 在这里处理获取到的 JSON 数据
    console.log(data);
  })
  .catch(error => {
    console.error('获取 JSON 数据时出错：', error);
  });
