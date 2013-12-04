includeJS=function(url,onload,allowCache){
	url=allowCache?url:url+'&nocache='+Math.random();
	url=url.split('?').length>1?url:url.replace(/\&/,'?');
	onload=typeof onload=="function"?onload:function(){};
	var js=document.createElement('script');
	js.setAttribute('src',url);
	js.addEventListener && function(){js.addEventListener('load',onload,false)}();
	js.onreadystatechange=function(){this.readyState=='complete' && onload.call()};
	document.getElementsByTagName('head').item(0).appendChild(js);
};

