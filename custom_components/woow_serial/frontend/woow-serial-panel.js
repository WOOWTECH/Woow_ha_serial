function t(t,e,s,i){var o,a=arguments.length,n=a<3?e:null===i?i=Object.getOwnPropertyDescriptor(e,s):i;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)n=Reflect.decorate(t,e,s,i);else for(var r=t.length-1;r>=0;r--)(o=t[r])&&(n=(a<3?o(n):a>3?o(e,s,n):o(e,s))||n);return a>3&&n&&Object.defineProperty(e,s,n),n}"function"==typeof SuppressedError&&SuppressedError;const e=globalThis,s=e.ShadowRoot&&(void 0===e.ShadyCSS||e.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,i=Symbol(),o=new WeakMap;let a=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==i)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(s&&void 0===t){const s=void 0!==e&&1===e.length;s&&(t=o.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&o.set(e,t))}return t}toString(){return this.cssText}};const n=(t,...e)=>{const s=1===t.length?t[0]:e.reduce((e,s,i)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(s)+t[i+1],t[0]);return new a(s,t,i)},r=s?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const s of t.cssRules)e+=s.cssText;return(t=>new a("string"==typeof t?t:t+"",void 0,i))(e)})(t):t,{is:d,defineProperty:l,getOwnPropertyDescriptor:c,getOwnPropertyNames:p,getOwnPropertySymbols:h,getPrototypeOf:u}=Object,m=globalThis,_=m.trustedTypes,v=_?_.emptyScript:"",$=m.reactiveElementPolyfillSupport,g=(t,e)=>t,b={toAttribute(t,e){switch(e){case Boolean:t=t?v:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let s=t;switch(e){case Boolean:s=null!==t;break;case Number:s=null===t?null:Number(t);break;case Object:case Array:try{s=JSON.parse(t)}catch(t){s=null}}return s}},f=(t,e)=>!d(t,e),y={attribute:!0,type:String,converter:b,reflect:!1,useDefault:!1,hasChanged:f};Symbol.metadata??=Symbol("metadata"),m.litPropertyMetadata??=new WeakMap;let w=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=y){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const s=Symbol(),i=this.getPropertyDescriptor(t,s,e);void 0!==i&&l(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){const{get:i,set:o}=c(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:i,set(e){const a=i?.call(this);o?.call(this,e),this.requestUpdate(t,a,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??y}static _$Ei(){if(this.hasOwnProperty(g("elementProperties")))return;const t=u(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(g("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(g("properties"))){const t=this.properties,e=[...p(t),...h(t)];for(const s of e)this.createProperty(s,t[s])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,s]of e)this.elementProperties.set(t,s)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const s=this._$Eu(t,e);void 0!==s&&this._$Eh.set(s,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const s=new Set(t.flat(1/0).reverse());for(const t of s)e.unshift(r(t))}else void 0!==t&&e.push(r(t));return e}static _$Eu(t,e){const s=e.attribute;return!1===s?void 0:"string"==typeof s?s:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((t,i)=>{if(s)t.adoptedStyleSheets=i.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const s of i){const i=document.createElement("style"),o=e.litNonce;void 0!==o&&i.setAttribute("nonce",o),i.textContent=s.cssText,t.appendChild(i)}})(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){const s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(void 0!==i&&!0===s.reflect){const o=(void 0!==s.converter?.toAttribute?s.converter:b).toAttribute(e,s.type);this._$Em=t,null==o?this.removeAttribute(i):this.setAttribute(i,o),this._$Em=null}}_$AK(t,e){const s=this.constructor,i=s._$Eh.get(t);if(void 0!==i&&this._$Em!==i){const t=s.getPropertyOptions(i),o="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:b;this._$Em=i;const a=o.fromAttribute(e,t.type);this[i]=a??this._$Ej?.get(i)??a,this._$Em=null}}requestUpdate(t,e,s,i=!1,o){if(void 0!==t){const a=this.constructor;if(!1===i&&(o=this[t]),s??=a.getPropertyOptions(t),!((s.hasChanged??f)(o,e)||s.useDefault&&s.reflect&&o===this._$Ej?.get(t)&&!this.hasAttribute(a._$Eu(t,s))))return;this.C(t,e,s)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:o},a){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,a??e??this[t]),!0!==o||void 0!==a)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),!0===i&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,s]of t){const{wrapped:t}=s,i=this[e];!0!==t||this._$AL.has(e)||void 0===i||this.C(e,void 0,s,i)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};w.elementStyles=[],w.shadowRootOptions={mode:"open"},w[g("elementProperties")]=new Map,w[g("finalized")]=new Map,$?.({ReactiveElement:w}),(m.reactiveElementVersions??=[]).push("2.1.2");const x=globalThis,k=t=>t,A=x.trustedTypes,S=A?A.createPolicy("lit-html",{createHTML:t=>t}):void 0,E="$lit$",C=`lit$${Math.random().toFixed(9).slice(2)}$`,P="?"+C,N=`<${P}>`,M=document,O=()=>M.createComment(""),T=t=>null===t||"object"!=typeof t&&"function"!=typeof t,R=Array.isArray,H="[ \t\n\f\r]",j=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,U=/-->/g,D=/>/g,W=RegExp(`>|${H}(?:([^\\s"'>=/]+)(${H}*=${H}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),L=/'/g,z=/"/g,B=/^(?:script|style|textarea|title)$/i,I=(t=>(e,...s)=>({_$litType$:t,strings:e,values:s}))(1),V=Symbol.for("lit-noChange"),F=Symbol.for("lit-nothing"),X=new WeakMap,G=M.createTreeWalker(M,129);function q(t,e){if(!R(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==S?S.createHTML(e):e}const J=(t,e)=>{const s=t.length-1,i=[];let o,a=2===e?"<svg>":3===e?"<math>":"",n=j;for(let e=0;e<s;e++){const s=t[e];let r,d,l=-1,c=0;for(;c<s.length&&(n.lastIndex=c,d=n.exec(s),null!==d);)c=n.lastIndex,n===j?"!--"===d[1]?n=U:void 0!==d[1]?n=D:void 0!==d[2]?(B.test(d[2])&&(o=RegExp("</"+d[2],"g")),n=W):void 0!==d[3]&&(n=W):n===W?">"===d[0]?(n=o??j,l=-1):void 0===d[1]?l=-2:(l=n.lastIndex-d[2].length,r=d[1],n=void 0===d[3]?W:'"'===d[3]?z:L):n===z||n===L?n=W:n===U||n===D?n=j:(n=W,o=void 0);const p=n===W&&t[e+1].startsWith("/>")?" ":"";a+=n===j?s+N:l>=0?(i.push(r),s.slice(0,l)+E+s.slice(l)+C+p):s+C+(-2===l?e:p)}return[q(t,a+(t[s]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),i]};class K{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let o=0,a=0;const n=t.length-1,r=this.parts,[d,l]=J(t,e);if(this.el=K.createElement(d,s),G.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(i=G.nextNode())&&r.length<n;){if(1===i.nodeType){if(i.hasAttributes())for(const t of i.getAttributeNames())if(t.endsWith(E)){const e=l[a++],s=i.getAttribute(t).split(C),n=/([.?@])?(.*)/.exec(e);r.push({type:1,index:o,name:n[2],strings:s,ctor:"."===n[1]?et:"?"===n[1]?st:"@"===n[1]?it:tt}),i.removeAttribute(t)}else t.startsWith(C)&&(r.push({type:6,index:o}),i.removeAttribute(t));if(B.test(i.tagName)){const t=i.textContent.split(C),e=t.length-1;if(e>0){i.textContent=A?A.emptyScript:"";for(let s=0;s<e;s++)i.append(t[s],O()),G.nextNode(),r.push({type:2,index:++o});i.append(t[e],O())}}}else if(8===i.nodeType)if(i.data===P)r.push({type:2,index:o});else{let t=-1;for(;-1!==(t=i.data.indexOf(C,t+1));)r.push({type:7,index:o}),t+=C.length-1}o++}}static createElement(t,e){const s=M.createElement("template");return s.innerHTML=t,s}}function Z(t,e,s=t,i){if(e===V)return e;let o=void 0!==i?s._$Co?.[i]:s._$Cl;const a=T(e)?void 0:e._$litDirective$;return o?.constructor!==a&&(o?._$AO?.(!1),void 0===a?o=void 0:(o=new a(t),o._$AT(t,s,i)),void 0!==i?(s._$Co??=[])[i]=o:s._$Cl=o),void 0!==o&&(e=Z(t,o._$AS(t,e.values),o,i)),e}class Q{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??M).importNode(e,!0);G.currentNode=i;let o=G.nextNode(),a=0,n=0,r=s[0];for(;void 0!==r;){if(a===r.index){let e;2===r.type?e=new Y(o,o.nextSibling,this,t):1===r.type?e=new r.ctor(o,r.name,r.strings,this,t):6===r.type&&(e=new ot(o,this,t)),this._$AV.push(e),r=s[++n]}a!==r?.index&&(o=G.nextNode(),a++)}return G.currentNode=M,i}p(t){let e=0;for(const s of this._$AV)void 0!==s&&(void 0!==s.strings?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}}class Y{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=F,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=Z(this,t,e),T(t)?t===F||null==t||""===t?(this._$AH!==F&&this._$AR(),this._$AH=F):t!==this._$AH&&t!==V&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>R(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==F&&T(this._$AH)?this._$AA.nextSibling.data=t:this.T(M.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:s}=t,i="number"==typeof s?this._$AC(t):(void 0===s.el&&(s.el=K.createElement(q(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{const t=new Q(i,this),s=t.u(this.options);t.p(e),this.T(s),this._$AH=t}}_$AC(t){let e=X.get(t.strings);return void 0===e&&X.set(t.strings,e=new K(t)),e}k(t){R(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let s,i=0;for(const o of t)i===e.length?e.push(s=new Y(this.O(O()),this.O(O()),this,this.options)):s=e[i],s._$AI(o),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const e=k(t).nextSibling;k(t).remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class tt{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,o){this.type=1,this._$AH=F,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=o,s.length>2||""!==s[0]||""!==s[1]?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=F}_$AI(t,e=this,s,i){const o=this.strings;let a=!1;if(void 0===o)t=Z(this,t,e,0),a=!T(t)||t!==this._$AH&&t!==V,a&&(this._$AH=t);else{const i=t;let n,r;for(t=o[0],n=0;n<o.length-1;n++)r=Z(this,i[s+n],e,n),r===V&&(r=this._$AH[n]),a||=!T(r)||r!==this._$AH[n],r===F?t=F:t!==F&&(t+=(r??"")+o[n+1]),this._$AH[n]=r}a&&!i&&this.j(t)}j(t){t===F?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class et extends tt{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===F?void 0:t}}class st extends tt{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==F)}}class it extends tt{constructor(t,e,s,i,o){super(t,e,s,i,o),this.type=5}_$AI(t,e=this){if((t=Z(this,t,e,0)??F)===V)return;const s=this._$AH,i=t===F&&s!==F||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,o=t!==F&&(s===F||i);i&&this.element.removeEventListener(this.name,this,s),o&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class ot{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){Z(this,t)}}const at=x.litHtmlPolyfillSupport;at?.(K,Y),(x.litHtmlVersions??=[]).push("3.3.3");const nt=globalThis;class rt extends w{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,s)=>{const i=s?.renderBefore??e;let o=i._$litPart$;if(void 0===o){const t=s?.renderBefore??null;i._$litPart$=o=new Y(e.insertBefore(O(),t),t,void 0,s??{})}return o._$AI(t),o})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return V}}rt._$litElement$=!0,rt.finalized=!0,nt.litElementHydrateSupport?.({LitElement:rt});const dt=nt.litElementPolyfillSupport;dt?.({LitElement:rt}),(nt.litElementVersions??=[]).push("4.2.2");const lt={attribute:!0,type:String,converter:b,reflect:!1,hasChanged:f},ct=(t=lt,e,s)=>{const{kind:i,metadata:o}=s;let a=globalThis.litPropertyMetadata.get(o);if(void 0===a&&globalThis.litPropertyMetadata.set(o,a=new Map),"setter"===i&&((t=Object.create(t)).wrapped=!0),a.set(s.name,t),"accessor"===i){const{name:i}=s;return{set(s){const o=e.get.call(this);e.set.call(this,s),this.requestUpdate(i,o,t,!0,s)},init(e){return void 0!==e&&this.C(i,void 0,t,e),e}}}if("setter"===i){const{name:i}=s;return function(s){const o=this[i];e.call(this,s),this.requestUpdate(i,o,t,!0,s)}}throw Error("Unsupported decorator location: "+i)};function pt(t){return(e,s)=>"object"==typeof s?ct(t,e,s):((t,e,s)=>{const i=e.hasOwnProperty(s);return e.constructor.createProperty(s,t),i?Object.getOwnPropertyDescriptor(e,s):void 0})(t,e,s)}function ht(t){return pt({...t,state:!0,attribute:!1})}class ut{constructor(t){this.hass=t}subscribe(t){return this.hass().connection.subscribeMessage(t,{type:"woow_serial/subscribe"})}snapshot(){return this.hass().callWS({type:"woow_serial/snapshot"})}send(t,e){return this.hass().callWS({type:"woow_serial/send",port_id:t,...e})}checksum(t,e,s=0){return this.hass().callWS({type:"woow_serial/checksum",hex:t,start:s,...e?{algorithm:e}:{}})}updateGroup(t,e){return this.hass().callWS({type:"woow_serial/catalog/update_group",group_id:t,...e})}updateRow(t,e){return this.hass().callWS({type:"woow_serial/catalog/update_row",row_id:t,alias:e})}deleteGroup(t){return this.hass().callWS({type:"woow_serial/catalog/delete",group_id:t})}deleteRow(t){return this.hass().callWS({type:"woow_serial/catalog/delete",row_id:t})}clearCatalog(t){return this.hass().callWS({type:"woow_serial/catalog/clear",...t?{port_id:t}:{}})}setPrefix(t,e){return this.hass().callWS({type:"woow_serial/catalog/prefix",port_id:t,length:e})}deleteSent(t){return this.hass().callWS({type:"woow_serial/mirror/delete",...t?{row_id:t}:{}})}saveDevice(t){return this.hass().callWS({type:"woow_serial/devices/save",device:t})}deleteDevice(t){return this.hass().callWS({type:"woow_serial/devices/delete",device_id:t})}runCommand(t,e,s){return this.hass().callWS({type:"woow_serial/devices/run",device_id:t,command_id:e,...void 0===s?{}:{value:s}})}preview(t,e,s,i){return this.hass().callWS({type:"woow_serial/template/preview",payload:t,format:e,params:s,...void 0===i?{}:{value:i}})}async listen(t,e=15){const s=await this.hass().callWS({type:"woow_serial/listen",port_id:t,timeout:e});return s.hex?{hex:s.hex,text:s.text??null}:null}testPattern(t,e,s,i){return this.hass().callWS({type:"woow_serial/pattern/test",pattern:t,format:e,port_id:s,params:i})}}function mt(){return Math.random().toString(16).slice(2,14).padEnd(12,"0")}function _t(t){return String(t&&"object"==typeof t&&"message"in t?t.message:t)}function vt(t,e){customElements.get(t)||customElements.define(t,e)}function $t(t){return{id:"",name:"",type:"switch",port_id:t,manufacturer:"",model:"",params:{},commands:[],actions:{},options:[],rules:[],sensors:[],buttons:[],ranges:{},poll_command:"",poll_interval:0}}function gt(t,e,s){if(!e)return[];const i=[];"boolean"==typeof e.power&&i.push(e.power?s("state_on"):s("state_off")),"number"==typeof e.position&&i.push(s("state_position",{n:Math.round(e.position)})),"number"==typeof e.brightness&&i.push(s("state_brightness",{n:Math.round(e.brightness/255*100)})),"number"==typeof e.volume&&i.push(s("state_volume",{n:Math.round(100*e.volume)})),!0===e.mute&&i.push(s("state_muted"));for(const t of["source","option"])"string"==typeof e[t]&&i.push(String(e[t]));"string"==typeof e.last_button&&i.push(s("state_last_button",{x:e.last_button}));for(const s of t.sensors.slice(0,4)){const t=e[`sensor:${s.id}`];null!=t&&i.push(`${s.name} ${t}${s.unit?` ${s.unit}`:""}`)}return i}function bt(t,e){return e?{pattern:`^${e.replace(/[.*+?^$\{}()|[\]]/g,"\\$&")}$`,format:"text"}:{pattern:t,format:"hex"}}function ft(t){return bt(t.hex,t.text)}function yt(t){return t.text?{payload:t.text,format:"text"}:{payload:t.hex,format:"hex"}}const wt={title:"WOOW Serial",tab_overview:"Overview",tab_monitor:"Monitor",tab_sendlog:"Send log",loading:"Loading…",kind_serial:"On-board serial",kind_external:"External",online:"Online",offline:"Offline",frames_in:"{n} in",frames_out:"{n} out",errors:"{n} errors",no_ports:"No ports yet. Add one under Settings › Devices & services › WOOW Serial.",send_title:"Send",port:"Port",mode_hex:"HEX",mode_text:"Text",ph_hex:"e.g. A5 5A 01 02",ph_text:"e.g. PWR ON\\r",append_checksum:"Append checksum",none:"None",from_byte:"from byte {n}",start_at:"starting at byte",wait_ms:"Wait for reply (ms)",send:"Send",sent:"Sent",reply:"Reply",sent_x:"Sent: {x}",reply_x:"Reply: {x}",reply_ms:"Reply {x} · {ms} ms",timeout:"No reply (timed out)",live_title:"Live",all_ports:"All ports",pause:"Pause",resume:"Resume",clear:"Clear",dropped:"{n} frames skipped (too many to show)",echo:"own echo",live_empty:"Nothing yet. Frames show up here as the ports send and receive.",origin_service:"service",origin_entity:"entity",origin_panel:"panel",origin_device:"device",origin_unknown:"other",monitor_empty:"No frames heard yet. Operate the devices on the RS485 / RS232 line (press a wall keypad, use the original remote) and the frames show up here, grouped by sender.",show_hidden:"Show hidden",hidden:"hidden",frames_count:"{n} frames",variants:"{n} kinds",per_second:"{n}/s",checksum_is:"Checksum: {name}",rename:"Rename",hide:"Hide",unhide:"Show",delete:"Delete",send_again:"Send again",copy:"Copy",copied:"Copied",group_by:"Group by the first",bytes:"bytes",apply:"Apply",prefix_confirm:"Change how this port's frames are grouped? Its current monitor records are cleared.",delete_group_confirm:"Delete this group? It comes back when its frames are heard again; use Hide to keep it out of the way.",alias_prompt:"Name (leave empty to clear)",sendlog_empty:"Nothing sent yet.",no_reply:"no reply",heard_by:"also heard by {ports}",times:"×{n}",clear_all:"Clear all",clear_all_confirm:"Clear the whole send log?",clear_port_confirm:"Clear the monitor records of {port}?",just_now:"just now",s_ago:"{n}s ago",m_ago:"{n}m ago",h_ago:"{n}h ago",d_ago:"{n}d ago",text_group:"Text",all_bytes:"(no grouping)",error:"Error: {msg}",checksum_2c:"two's complement",tab_devices:"Devices",add_device:"Add device",devices_empty:"No devices yet. Add one, or pick frames in the Monitor tab and choose Add to device.",type_switch:"Switch",type_light:"Light",type_cover:"Cover",type_media_player:"Media player",type_select:"Select",type_other:"Buttons only",edit:"Edit",save:"Save",saved:"Saved",cancel:"Cancel",back:"Back",delete_device:"Delete device",confirm_delete_device:"Delete {name}? Its entities are removed with it.",unsaved:"Unsaved changes",sec_basic:"Device",name:"Name",type:"Type",manufacturer:"Brand",model:"Model",sec_params:"Parameters",params_hint:"{name} in commands and patterns is replaced by this HEX value (a device address, say).",param_name:"Name",param_value:"HEX value",add_param:"Add parameter",sec_commands:"Commands",commands_hint:"HEX: 55 {addr} 03 {value:u8} {crc16_modbus}   Text: VOL {value:03d}\\r",add_command:"Add command",command_name:"Command name",format:"Format",format_hex:"HEX",format_text:"Text",repeat:"Send times",wait_reply:"Wait for reply (ms)",test:"Test",save_first:"Save the device first, then test.",value_prompt:"This command takes a value. What value?",will_send:"Sends {x}",sec_actions:"Entity actions",actions_hint:"Map the entity's functions to commands. A function without a command does not appear on the entity.",not_used:"—",act_turn_on:"Turn on",act_turn_off:"Turn off",act_set_brightness:"Set brightness",act_open:"Open",act_close:"Close",act_stop:"Stop",act_set_position:"Set position",act_volume_up:"Volume up",act_volume_down:"Volume down",act_set_volume:"Set volume",act_mute_on:"Mute",act_mute_off:"Unmute",act_play:"Play",act_pause:"Pause",act_next:"Next",act_previous:"Previous",sec_options:"Options / sources",options_hint:"Sources of a media player, or the choices of a select; picking one sends its command.",option_name:"Option",add_option:"Add option",sec_ranges:"Value ranges",ranges_hint:"The device's own numbers at 0 % and at 100 % (e.g. volume 0–60). Reversed (100–0) works too.",range_at0:"at 0 %",range_at100:"at 100 %",field_power:"Power",field_brightness:"Brightness",field_position:"Position",field_volume:"Volume",field_mute:"Mute",field_source:"Source",field_option:"Option",field_playback:"Playback",sec_rules:"State feedback",rules_hint:"When a received frame matches, the state is updated. ?? any byte · {pos:u8} reads a number · {addr} must match · {crc16_modbus} must be right · * anything after. Text: a regular expression, e.g. ^PWR=(?P<p>\\d)",add_rule:"Add rule",pattern:"Pattern",field:"State",value:"Value",value_hint:"A fixed value (on, off, HDMI1) or {capture}",try_pattern:"Try",matches:"{n} frames in the monitor match",no_matches:"No frame in the monitor matches",sec_sensors:"Sensors",sensors_hint:"Numbers read out of frames, e.g. temperature = {t:s16be} × 0.1",add_sensor:"Add sensor",capture:"Capture",scale:"× scale",offset:"+ offset",unit:"Unit",device_class:"Device class",precision:"Decimals",sec_poll:"Polling",poll_hint:"Send a query command regularly so the device reports its state.",poll_command:"Query command",poll_interval:"Every (s)",no_poll:"No polling",add_to_device:"Add to device",choose_device:"Device",new_device:"＋ New device",added_to:"Added to {name}",state_on:"On",state_off:"Off",state_position:"Position {n} %",state_brightness:"Brightness {n} %",state_volume:"Volume {n} %",state_muted:"Muted",entities_count:"{n} entities",remove:"Remove",type_keypad:"Keypad",sec_buttons:"Buttons",buttons_hint:'Each button is the frame it sends. Press LISTEN and then the physical button to learn it. A button fires the device trigger "button pressed" in automations, and can also drive another device by itself. Works for any input that sends frames on its own (door contacts, sensors).',add_button:"Add button",button_name:"Button name",debounce:"Same press within (ms)",listen:"Listen",listening:"Press the physical button now… (15 s)",listen_timeout:"Nothing heard within 15 s.",heard:"Heard {x}",binding:"Also does",binding_none:"(trigger only)",binding_target:"Device",act_toggle:"Toggle on / off",option_x:"Option: {x}",command_x:"Command: {x}",value_pct:"Value %",make_button:"Make a button",choose_keypad:"Keypad",new_keypad:"＋ New keypad",state_last_button:"Last: {x}",dev_no_buttons_for_type:"Only a keypad has buttons.",dev_button_name:"Button names must be filled in and different: {button}",dev_button_pattern:"Button {button}: {template}",dev_button_debounce:"Button {button}: the repeat window is 0 to 10000 ms.",dev_binding_target:"Button {button}: the device it drives no longer exists.",dev_binding_action:"Button {button}: that device cannot do {action}.",dev_binding_value:"Button {button}: give a value from 0 to 100 %.",dev_no_name:"Give the device a name.",dev_bad_type:"Unknown device type.",dev_no_port:"Pick a port.",dev_bad_param_name:"Parameter name {param}: letters, digits and _ only.",dev_bad_param:"Parameter {param} is not HEX: {value}",dev_command_no_name:"A command has no name.",dev_command_duplicate:"Two commands are called {command}.",dev_command_format:"Command {command}: this format does not suit the port.",dev_command_template:"Command {command}: {template}",dev_command_limits:"Command {command}: send times or wait time out of range.",dev_bad_action:"This type has no action {action}.",dev_action_command:"The command for {action} no longer exists.",dev_no_options_for_type:"This type has no options.",dev_option_name:"Option names must be filled in and different: {option}",dev_option_command:"Option {option} has no command.",dev_rule_field:"This type has no state {field}.",dev_rule_pattern:"State feedback: {template}",dev_rule_capture:"A state rule uses {capture}, which its pattern does not capture.",dev_sensor_no_name:"A sensor has no name.",dev_sensor_pattern:"Sensor {sensor}: {template}",dev_sensor_capture:"Sensor {sensor}: the pattern does not capture {capture}.",dev_bad_range:"Invalid value range: {field}",dev_poll_command:"The query command no longer exists.",dev_poll_interval:"Polling interval: 1 to 86400 seconds.",dev_malformed:"Malformed data: {detail}",tpl_bad_field:"cannot read {t_field}",tpl_bad_type:"unknown type {t_type}",tpl_bad_token:"cannot read “{t_text}” (character {t_at})",tpl_odd_hex:"odd number of HEX digits: {t_text}",tpl_bad_param:"parameter {t_field} is not HEX",tpl_not_number:"{t_field} is not a number",tpl_range:"{t_field} = {t_value} does not fit its type",tpl_wildcard_in_command:"?? and * belong in patterns, not in commands",tpl_no_value:"no value for {t_field}",tpl_bad_format:"format {t_spec} does not suit {t_field}",tpl_bad_escape:"bad escape",tpl_bad_regex:"bad regular expression: {t_detail}",tpl_rest_not_last:"* must come last",tpl_capture_needs_type:"{t_field} needs a type to be read, e.g. {t_field}:u8"},xt={title:"WOOW 串口",tab_overview:"總覽",tab_monitor:"監看",tab_sendlog:"發送紀錄",loading:"載入中…",kind_serial:"本機串口",kind_external:"外接",online:"連線中",offline:"離線",frames_in:"收 {n} 筆",frames_out:"發 {n} 筆",errors:"錯誤 {n}",no_ports:"還沒有埠。請到「設定 › 裝置與服務 › WOOW Serial」新增。",send_title:"手動發送",port:"埠",mode_hex:"HEX",mode_text:"文字",ph_hex:"例如 A5 5A 01 02",ph_text:"例如 PWR ON\\r",append_checksum:"附加校驗碼",none:"不加",from_byte:"從第 {n} 個位元組算",start_at:"從第幾個位元組算",wait_ms:"等待回覆（毫秒）",send:"送出",sent:"已送出",reply:"回覆",sent_x:"已送出：{x}",reply_x:"回覆：{x}",reply_ms:"回覆 {x}（{ms} 毫秒）",timeout:"沒有回覆（逾時）",live_title:"即時資料",all_ports:"全部埠",pause:"暫停",resume:"繼續",clear:"清除",dropped:"略過 {n} 筆（太多，來不及顯示）",echo:"自己送出的回音",live_empty:"還沒有資料。埠收發資料時會即時顯示在這裡。",origin_service:"服務",origin_entity:"實體",origin_panel:"面板",origin_device:"裝置",origin_unknown:"其他",monitor_empty:"還沒有收到任何訊框。在 RS485／RS232 線路上操作設備（按牆面按鍵、用原廠遙控器），收到的訊框會依來源分組出現在這裡。",show_hidden:"顯示隱藏的",hidden:"已隱藏",frames_count:"{n} 筆",variants:"{n} 種",per_second:"每秒 {n} 筆",checksum_is:"校驗碼：{name}",rename:"命名",hide:"隱藏",unhide:"取消隱藏",delete:"刪除",send_again:"再送一次",copy:"複製",copied:"已複製",group_by:"依前幾個位元組分組",bytes:"個位元組",apply:"套用",prefix_confirm:"要改這個埠的分組方式嗎？這個埠目前的監看紀錄會清除。",delete_group_confirm:"要刪除這個群組嗎？再收到同樣的訊框時會重新出現；想讓它不再出現請用「隱藏」。",alias_prompt:"名稱（留空＝清除名稱）",sendlog_empty:"還沒有發送紀錄。",no_reply:"沒有回覆",heard_by:"{ports} 也收到了",times:"{n} 次",clear_all:"全部清除",clear_all_confirm:"要清除全部發送紀錄嗎？",clear_port_confirm:"要清除 {port} 的監看紀錄嗎？",just_now:"剛剛",s_ago:"{n} 秒前",m_ago:"{n} 分鐘前",h_ago:"{n} 小時前",d_ago:"{n} 天前",text_group:"文字",all_bytes:"（不分組）",error:"錯誤：{msg}",checksum_2c:"補數",tab_devices:"裝置",add_device:"新增裝置",devices_empty:"還沒有裝置。按「新增裝置」，或在「監看」分頁挑訊框，按「加到裝置」。",type_switch:"開關",type_light:"燈光",type_cover:"窗簾／遮陽",type_media_player:"影音設備",type_select:"選擇器",type_other:"只有按鈕",edit:"編輯",save:"儲存",saved:"已儲存",cancel:"取消",back:"返回",delete_device:"刪除裝置",confirm_delete_device:"要刪除「{name}」嗎？它的實體會一起移除。",unsaved:"有尚未儲存的變更",sec_basic:"裝置",name:"名稱",type:"類型",manufacturer:"廠牌",model:"型號",sec_params:"參數",params_hint:"指令和樣式裡的 {名稱} 會換成這裡的 HEX 值（例如設備位址）。",param_name:"名稱",param_value:"HEX 值",add_param:"新增參數",sec_commands:"指令",commands_hint:"HEX：55 {addr} 03 {value:u8} {crc16_modbus}　文字：VOL {value:03d}\\r",add_command:"新增指令",command_name:"指令名稱",format:"格式",format_hex:"HEX",format_text:"文字",repeat:"送幾次",wait_reply:"等回覆（毫秒）",test:"測試",save_first:"請先儲存裝置再測試。",value_prompt:"這個指令要帶數值，要送多少？",will_send:"會送出 {x}",sec_actions:"實體功能對應",actions_hint:"把實體的功能對應到指令；沒有對應指令的功能不會出現在實體上。",not_used:"—",act_turn_on:"開啟",act_turn_off:"關閉",act_set_brightness:"設定亮度",act_open:"打開",act_close:"關上",act_stop:"停止",act_set_position:"設定位置",act_volume_up:"音量＋",act_volume_down:"音量－",act_set_volume:"設定音量",act_mute_on:"靜音",act_mute_off:"取消靜音",act_play:"播放",act_pause:"暫停",act_next:"下一個",act_previous:"上一個",sec_options:"選項／訊源",options_hint:"影音設備的訊源，或選擇器的選項；選了就送出對應的指令。",option_name:"選項",add_option:"新增選項",sec_ranges:"數值範圍",ranges_hint:"設備自己的數值在 0% 和 100% 時是多少（例如音量 0～60）；反過來（100～0）也可以。",range_at0:"0% 時",range_at100:"100% 時",field_power:"電源",field_brightness:"亮度",field_position:"位置",field_volume:"音量",field_mute:"靜音",field_source:"訊源",field_option:"選項",field_playback:"播放狀態",sec_rules:"狀態回讀",rules_hint:"收到符合樣式的訊框就更新狀態。?? 任一位元組 · {pos:u8} 讀出數字 · {addr} 要相符 · {crc16_modbus} 要正確 · * 後面不管。文字用正規表示式，例如 ^PWR=(?P<p>\\d)",add_rule:"新增規則",pattern:"樣式",field:"狀態",value:"值",value_hint:"固定值（on、off、HDMI1）或 {擷取名稱}",try_pattern:"試比對",matches:"監看中有 {n} 筆符合",no_matches:"監看中沒有符合的訊框",sec_sensors:"感測器",sensors_hint:"從訊框讀出數值，例如溫度＝{t:s16be} × 0.1",add_sensor:"新增感測器",capture:"擷取名稱",scale:"× 倍率",offset:"＋ 偏移",unit:"單位",device_class:"類別",precision:"小數位數",sec_poll:"輪詢",poll_hint:"定時送出查詢指令，讓設備回報狀態。",poll_command:"查詢指令",poll_interval:"每幾秒",no_poll:"不輪詢",add_to_device:"加到裝置",choose_device:"裝置",new_device:"＋ 新增裝置",added_to:"已加到「{name}」",state_on:"開",state_off:"關",state_position:"位置 {n}%",state_brightness:"亮度 {n}%",state_volume:"音量 {n}%",state_muted:"靜音",entities_count:"{n} 個實體",remove:"移除",type_keypad:"按鍵面板",sec_buttons:"按鍵",buttons_hint:"每個按鍵就是它送出的訊框。按「聆聽」再按實體按鍵就能學起來。按鍵會在自動化裡觸發「按下」，也可以直接控制另一個裝置。任何會主動送訊框的輸入設備（門磁、感應器）也能這樣用。",add_button:"新增按鍵",button_name:"按鍵名稱",debounce:"幾毫秒內算同一次",listen:"聆聽",listening:"請現在按下實體按鍵…（15 秒內）",listen_timeout:"15 秒內沒有收到訊框。",heard:"收到 {x}",binding:"同時執行",binding_none:"（只觸發，不直接控制）",binding_target:"裝置",act_toggle:"切換開／關",option_x:"選項：{x}",command_x:"指令：{x}",value_pct:"數值 %",make_button:"做成按鍵",choose_keypad:"按鍵面板",new_keypad:"＋ 新增按鍵面板",state_last_button:"最後按下：{x}",dev_no_buttons_for_type:"只有按鍵面板可以有按鍵。",dev_button_name:"按鍵名稱要填而且不能重複：{button}",dev_button_pattern:"按鍵「{button}」：{template}",dev_button_debounce:"按鍵「{button}」：同一次的時間要在 0～10000 毫秒之間。",dev_binding_target:"按鍵「{button}」：要控制的裝置已經不存在。",dev_binding_action:"按鍵「{button}」：那個裝置沒有「{action}」這個動作。",dev_binding_value:"按鍵「{button}」：請填 0～100% 的數值。",dev_no_name:"請填裝置名稱。",dev_bad_type:"不認得的裝置類型。",dev_no_port:"請選擇埠。",dev_bad_param_name:"參數名稱「{param}」只能用英文字母、數字和底線。",dev_bad_param:"參數「{param}」不是 HEX：{value}",dev_command_no_name:"有指令沒有名稱。",dev_command_duplicate:"有兩個指令都叫「{command}」。",dev_command_format:"指令「{command}」的格式不適用這個埠。",dev_command_template:"指令「{command}」：{template}",dev_command_limits:"指令「{command}」的次數或等待時間超出範圍。",dev_bad_action:"這個類型沒有「{action}」功能。",dev_action_command:"「{action}」對應的指令已經不存在。",dev_no_options_for_type:"這個類型沒有選項。",dev_option_name:"選項名稱要填而且不能重複：{option}",dev_option_command:"選項「{option}」沒有對應的指令。",dev_rule_field:"這個類型沒有「{field}」狀態。",dev_rule_pattern:"狀態回讀：{template}",dev_rule_capture:"狀態規則用到「{capture}」，但樣式裡沒有擷取它。",dev_sensor_no_name:"有感測器沒有名稱。",dev_sensor_pattern:"感測器「{sensor}」：{template}",dev_sensor_capture:"感測器「{sensor}」的樣式裡沒有擷取「{capture}」。",dev_bad_range:"數值範圍錯誤：{field}",dev_poll_command:"查詢指令已經不存在。",dev_poll_interval:"輪詢間隔要在 1～86400 秒之間。",dev_malformed:"資料格式錯誤：{detail}",tpl_bad_field:"看不懂「{t_field}」",tpl_bad_type:"不認得的型別 {t_type}",tpl_bad_token:"看不懂「{t_text}」（第 {t_at} 個字）",tpl_odd_hex:"HEX 位數是奇數：{t_text}",tpl_bad_param:"參數 {t_field} 不是 HEX",tpl_not_number:"{t_field} 不是數字",tpl_range:"{t_field} = {t_value} 超出它的型別範圍",tpl_wildcard_in_command:"?? 和 * 只能用在樣式，不能用在指令",tpl_no_value:"缺少 {t_field} 的值",tpl_bad_format:"格式 {t_spec} 不適用 {t_field}",tpl_bad_escape:"跳脫字元錯誤",tpl_bad_regex:"正規表示式錯誤：{t_detail}",tpl_rest_not_last:"* 只能放在最後",tpl_capture_needs_type:"{t_field} 要加型別才能讀出數字，例如 {t_field}:u8"};function kt(t){const e=t.toLowerCase().startsWith("zh")?xt:wt;return(t,s)=>{let i=e[t]??wt[t]??t;if(s)for(const[t,e]of Object.entries(s))i=i.split(`{${t}}`).join(String(e));return i}}const At={crc16_modbus:"CRC16/Modbus",crc16_ccitt:"CRC16/CCITT",crc16_xmodem:"CRC16/XMODEM",sum16:"SUM16",crc8:"CRC8",crc8_maxim:"CRC8/Maxim",xor8:"XOR8",sum8:"SUM8",sum8_neg:"SUM8"};function St(t,e){const[s,i]=t.split("@");let o=At[s]??s;return"sum8_neg"===s&&(o+=` ${e("checksum_2c")}`),i?`${o} · ${e("from_byte",{n:Number(i)+1})}`:o}function Et(t,e){const s=Math.max(0,Date.now()/1e3-t);return s<5?e("just_now"):s<60?e("s_ago",{n:Math.floor(s)}):s<3600?e("m_ago",{n:Math.floor(s/60)}):s<86400?e("h_ago",{n:Math.floor(s/3600)}):e("d_ago",{n:Math.floor(s/86400)})}function Ct(t){return t in wt}function Pt(t,e,s){if(!t)return e("origin_unknown");if(t.startsWith("device:"))return s?.(t.split(":")[1])??e("origin_device");const i=`origin_${t}`;return Ct(i)?e(i):t}function Nt(t,e){const s={};for(const[e,i]of Object.entries(t))"code"!==e&&(s[e]="number"==typeof i?i:String(i));if("string"==typeof t.template_code){const i=`tpl_${t.template_code}`;s.template=Ct(i)?e(i,s):t.template_code}for(const i of[`dev_${t.code}`,`tpl_${t.code}`])if(Ct(i))return e(i,s);return`${t.code} ${JSON.stringify(s)}`}const Mt=n`
  :host {
    display: block;
    color: var(--primary-text-color);
    font-family: var(--paper-font-body1_-_font-family, Roboto, "Noto Sans TC", sans-serif);
  }
  .card {
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: var(--ha-card-border-radius, 12px);
    padding: 16px;
    margin-bottom: 16px;
  }
  .card h2 {
    margin: 0 0 12px;
    font-size: 1.1em;
    font-weight: 500;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  .grow {
    flex: 1 1 auto;
    min-width: 0;
  }
  .muted {
    color: var(--secondary-text-color);
    font-size: 0.9em;
  }
  .mono {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 0.92em;
    word-break: break-all;
  }
  .chip {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 0.8em;
    line-height: 1.6;
    background: var(--secondary-background-color, #eee);
    color: var(--secondary-text-color);
    white-space: nowrap;
  }
  .chip.ok {
    background: rgba(67, 160, 71, 0.15);
    color: var(--success-color, #43a047);
  }
  .chip.warn {
    background: rgba(255, 152, 0, 0.15);
    color: var(--warning-color, #ff9800);
  }
  .chip.bad {
    background: rgba(219, 68, 55, 0.12);
    color: var(--error-color, #db4437);
  }
  .chip.info {
    background: rgba(3, 169, 244, 0.14);
    color: var(--info-color, #039be5);
  }
  button {
    font: inherit;
    border: 1px solid var(--divider-color, #ccc);
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    border-radius: 8px;
    padding: 4px 10px;
    cursor: pointer;
  }
  button:hover {
    border-color: var(--primary-color);
  }
  button.primary {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }
  button.link {
    border: none;
    background: none;
    color: var(--primary-color);
    padding: 2px 4px;
  }
  button.danger {
    color: var(--error-color, #db4437);
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  input,
  select {
    font: inherit;
    color: var(--primary-text-color);
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #ccc);
    border-radius: 8px;
    padding: 6px 8px;
    min-width: 0;
  }
  input:focus,
  select:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: -1px;
  }
  .empty {
    padding: 24px 8px;
    text-align: center;
    color: var(--secondary-text-color);
  }
  .rx {
    color: var(--success-color, #43a047);
  }
  .tx {
    color: var(--info-color, #039be5);
  }
`,Ot=t=>t.target.value,Tt=(t,e=0)=>{const s=Number(Ot(t));return Number.isFinite(s)?s:e};class Rt extends rt{constructor(){super(...arguments),this.devices=[],this.types={},this.valueActions={},this.ports=[],this.params=[],this.dirty=!1,this.status=null,this.busy=!1,this.previews={},this.tried={},this.listening=null,this.timers=new Map}willUpdate(t){!t.has("device")||this.draft&&this.device.id===this.loadedId&&this.dirty||this.load(this.device)}disconnectedCallback(){super.disconnectedCallback();for(const t of this.timers.values())window.clearTimeout(t)}load(t){const e=structuredClone(t);delete e.entities,this.draft=e,this.params=Object.entries(e.params),this.loadedId=t.id,this.dirty=!1;for(const t of e.commands)this.schedulePreview(t,0)}get spec(){return this.types[this.draft.type]??{platform:null,actions:[],fields:[]}}paramObject(){return Object.fromEntries(this.params.filter(([t])=>t.trim()).map(([t,e])=>[t.trim(),e.trim()]))}change(t){const e=structuredClone(this.draft);t(e),this.draft=e,this.dirty=!0}label(t,e){const s=`${t}${e}`;return Ct(s)?this.t(s):e}schedulePreview(t,e=300){window.clearTimeout(this.timers.get(t.id)),this.timers.set(t.id,window.setTimeout(async()=>{let e;try{e=await this.api.preview(t.payload,t.format,this.paramObject(),0)}catch(t){e={error:{code:"malformed",detail:_t(t)}}}this.previews={...this.previews,[t.id]:e}},e))}previewAll(){for(const t of this.draft.commands)this.schedulePreview(t)}async tryPattern(t,e,s){const i=this.t;try{const o=await this.api.testPattern(e,s,this.draft.port_id,this.paramObject());let a;if(o.error)a={ok:!1,text:Nt(o.error,i)};else if(o.matches?.length){const t=o.matches.slice(0,3).map(t=>`${t.frame}  ${JSON.stringify(t.captures)}`).join("\n");a={ok:!0,text:`${i("matches",{n:o.matches.length})}\n${t}`}}else a={ok:!1,text:i("no_matches")};this.tried={...this.tried,[t]:a}}catch(e){this.tried={...this.tried,[t]:{ok:!1,text:i("error",{msg:_t(e)})}}}}async listenFor(t){const e=this.t;this.listening=t.id,this.tried={...this.tried,[t.id]:{ok:!0,text:e("listening")}};try{const s=await this.api.listen(this.draft.port_id,15);if(!s)return void(this.tried={...this.tried,[t.id]:{ok:!1,text:e("listen_timeout")}});const i=bt(s.hex,s.text);this.change(e=>{const s=e.buttons.find(e=>e.id===t.id);s&&(s.pattern=i.pattern,s.format=i.format)}),this.tried={...this.tried,[t.id]:{ok:!0,text:e("heard",{x:s.hex})}}}catch(s){this.tried={...this.tried,[t.id]:{ok:!1,text:e("error",{msg:_t(s)})}}}finally{this.listening=null}}bindLabel(t,e){const s=this.t;if("toggle"===e)return s("act_toggle");if(e.startsWith("option:"))return s("option_x",{x:e.slice(7)});if(e.startsWith("command:")){const i=e.slice(8);return s("command_x",{x:t?.commands.find(t=>t.id===i)?.name??i})}return this.label("act_",e)}async test(t){const e=this.t;if(!this.draft.id||this.dirty)return void(this.status={ok:!1,text:e("save_first")});let s;if(this.previews[t.id]?.fields?.includes("value")){const t=window.prompt(e("value_prompt"),"0");if(null===t)return;s=Number(t)}try{const i=await this.api.runCommand(this.draft.id,t.id,s);this.status={ok:!0,text:e("sent_x",{x:i.sent})+(i.reply?`   ${e("reply_x",{x:i.reply})}`:"")}}catch(t){this.status={ok:!1,text:e("error",{msg:_t(t)})}}}async save(){const t=this.t,e={...structuredClone(this.draft),params:this.paramObject()};this.busy=!0;try{const s=await this.api.saveDevice(e);if(s.error)return void(this.status={ok:!1,text:Nt(s.error,t)});s.device&&this.load(s.device),this.status={ok:!0,text:t("saved")}}catch(e){this.status={ok:!1,text:t("error",{msg:_t(e)})}}finally{this.busy=!1}}async removeDevice(){if(window.confirm(this.t("confirm_delete_device",{name:this.draft.name})))try{await this.api.deleteDevice(this.draft.id),this.dispatchEvent(new CustomEvent("close",{bubbles:!0,composed:!0}))}catch(t){this.status={ok:!1,text:this.t("error",{msg:_t(t)})}}}leave(){this.dirty&&!window.confirm(`${this.t("unsaved")} — ${this.t("back")}?`)||this.dispatchEvent(new CustomEvent("close",{bubbles:!0,composed:!0}))}formatSelect(t,e){return I`<select class="small" @change=${t=>e(Ot(t))}>
      ${["hex","text"].map(e=>I`<option value=${e} ?selected=${e===t}>${this.label("format_",e)}</option>`)}
    </select>`}commandSelect(t,e,s){return I`<select @change=${t=>e(Ot(t))}>
      <option value="" ?selected=${!t}>${s??this.t("not_used")}</option>
      ${this.draft.commands.map(e=>I`<option value=${e.id} ?selected=${e.id===t}>${e.name||"?"}</option>`)}
    </select>`}renderBasic(){const t=this.t,e=this.draft;return I`<div class="card">
      <h2>${t("sec_basic")}</h2>
      <div class="form">
        <label>${t("name")}<input .value=${e.name} @input=${t=>this.change(e=>e.name=Ot(t))} /></label>
        <label
          >${t("type")}
          <select
            @change=${t=>this.change(e=>{e.type=Ot(t);const s=this.types[e.type];e.actions=Object.fromEntries(Object.entries(e.actions).filter(([t])=>s?.actions.includes(t))),s?.options||(e.options=[]),e.rules=e.rules.filter(t=>s?.fields.includes(t.field))})}
          >
            ${Object.keys(this.types).map(t=>I`<option value=${t} ?selected=${t===e.type}>${this.label("type_",t)}</option>`)}
          </select>
        </label>
        <label
          >${t("port")}
          <select @change=${t=>this.change(e=>e.port_id=Ot(t))}>
            ${this.ports.map(t=>I`<option value=${t.id} ?selected=${t.id===e.port_id}>${t.name}</option>`)}
          </select>
        </label>
        <label>${t("manufacturer")}<input .value=${e.manufacturer} @input=${t=>this.change(e=>e.manufacturer=Ot(t))} /></label>
        <label>${t("model")}<input .value=${e.model} @input=${t=>this.change(e=>e.model=Ot(t))} /></label>
      </div>
      ${this.state&&e.id?I`<div class="row" style="margin-top:10px">
            ${gt(e,this.state,t).map(t=>I`<span class="chip info">${t}</span>`)}
          </div>`:F}
    </div>`}renderParams(){const t=this.t,e=(t,e,s)=>{const i=this.params.map(t=>[...t]);i[t][e]=s,this.params=i,this.dirty=!0,this.previewAll()};return I`<div class="card">
      <h2>${t("sec_params")}</h2>
      <div class="hint">${t("params_hint")}</div>
      ${this.params.map(([s,i],o)=>I`<div class="row" style="margin-bottom:6px">
          <input class="small mono" placeholder=${t("param_name")} .value=${s} @input=${t=>e(o,0,Ot(t))} />
          <input class="grow mono" placeholder=${t("param_value")} .value=${i} @input=${t=>e(o,1,Ot(t))} />
          <button class="link danger" @click=${()=>{this.params=this.params.filter((t,e)=>e!==o),this.dirty=!0,this.previewAll()}}>${t("remove")}</button>
        </div>`)}
      <button @click=${()=>{this.params=[...this.params,[this.params.length?"":"addr",""]],this.dirty=!0}}>${t("add_param")}</button>
    </div>`}renderCommands(){const t=this.t,e=(t,e)=>{this.change(s=>e(s.commands[t])),this.schedulePreview(this.draft.commands[t])};return I`<div class="card">
      <h2>${t("sec_commands")}</h2>
      <div class="hint mono">${t("commands_hint")}</div>
      ${this.draft.commands.map((s,i)=>{const o=this.previews[s.id];return I`<div class="item">
          <div class="row">
            <input class="small" placeholder=${t("command_name")} .value=${s.name} @input=${t=>e(i,e=>e.name=Ot(t))} />
            ${this.formatSelect(s.format,t=>e(i,e=>e.format=t))}
            <input class="wide mono" .value=${s.payload} @input=${t=>e(i,e=>e.payload=Ot(t))} />
          </div>
          <div class="row muted">
            <span>${t("repeat")}</span>
            <input class="tiny" type="number" min="1" max="20" .value=${String(s.repeat)}
              @input=${t=>e(i,e=>e.repeat=Math.min(20,Math.max(1,Tt(t,1))))} />
            <span>${t("wait_reply")}</span>
            <input class="small" type="number" min="0" max="60000" step="100" .value=${String(s.wait_ms)}
              @input=${t=>e(i,e=>e.wait_ms=Math.max(0,Tt(t)))} />
            <span class="grow"></span>
            <button class="link" @click=${()=>this.test(s)}>${t("test")}</button>
            <button class="link danger" @click=${()=>this.change(t=>{t.commands.splice(i,1),t.actions=Object.fromEntries(Object.entries(t.actions).filter(([,t])=>t!==s.id)),t.options=t.options.filter(t=>t.command!==s.id),t.poll_command===s.id&&(t.poll_command="")})}>${t("remove")}</button>
          </div>
          ${o?.error?I`<div class="note bad">${Nt(o.error,t)}</div>`:o?.sent?I`<div class="note ok mono">${t("will_send",{x:o.sent})}${o.fields?.includes("value")?"  (value = 0)":""}</div>`:F}
        </div>`})}
      <button @click=${()=>{const t={id:mt(),name:"",payload:"",format:"hex",repeat:1,gap_ms:100,wait_ms:0};this.change(e=>e.commands.push(t))}}>${t("add_command")}</button>
    </div>`}renderActions(){const t=this.t,e=this.spec.actions;return e.length?I`<div class="card">
      <h2>${t("sec_actions")}</h2>
      <div class="hint">${t("actions_hint")}</div>
      <div class="actions-grid">
        ${e.map(t=>I`<label>${this.label("act_",t)}
            ${this.commandSelect(this.draft.actions[t]??"",e=>this.change(s=>{e?s.actions[t]=e:delete s.actions[t]}))}</label>`)}
      </div>
    </div>`:F}renderButtons(){const t=this.t;if(!this.spec.buttons)return F;const e=this.devices.filter(t=>t.id&&t.id!==this.draft.id&&(t.bindable?.length??0)>0);return I`<div class="card">
      <h2>${t("sec_buttons")}</h2>
      <div class="hint">${t("buttons_hint")}</div>
      ${this.draft.buttons.map((s,i)=>{const o=this.tried[s.id],a=t=>this.change(e=>t(e.buttons[i])),n=this.devices.find(t=>t.id===s.target);return I`<div class="item">
          <div class="row">
            <input class="small" placeholder=${t("button_name")} .value=${s.name} @input=${t=>a(e=>e.name=Ot(t))} />
            <input class="wide mono" placeholder=${t("pattern")} .value=${s.pattern} @input=${t=>a(e=>e.pattern=Ot(t))} />
            ${this.formatSelect(s.format,t=>a(e=>e.format=t))}
          </div>
          <div class="row muted">
            <span>${t("debounce")}</span>
            <input class="small" type="number" min="0" max="10000" step="50" .value=${String(s.debounce_ms)}
              @input=${t=>a(e=>e.debounce_ms=Math.min(1e4,Math.max(0,Math.round(Tt(t,300)))))} />
            <span>${t("binding")}</span>
            <select @change=${t=>a(e=>{e.target=Ot(t),e.action="",e.value=null})}>
              <option value="" ?selected=${!s.target}>${t("binding_none")}</option>
              ${e.map(t=>I`<option value=${t.id} ?selected=${t.id===s.target}>${t.name}</option>`)}
            </select>
            ${s.target?I`<select @change=${t=>a(e=>e.action=Ot(t))}>
                  <option value="" ?selected=${!s.action}>${t("not_used")}</option>
                  ${(n?.bindable??[]).map(t=>I`<option value=${t} ?selected=${t===s.action}>${this.bindLabel(n,t)}</option>`)}
                </select>`:F}
            ${s.action in this.valueActions?I`<span>${t("value_pct")}</span>
                  <input class="tiny" type="number" min="0" max="100" .value=${null===s.value?"":String(s.value)}
                    @input=${t=>a(e=>e.value=""===Ot(t)?null:Math.min(100,Math.max(0,Tt(t))))} />`:F}
            <span class="grow"></span>
            <button class="link" ?disabled=${null!==this.listening} @click=${()=>this.listenFor(s)}>${t("listen")}</button>
            <button class="link" @click=${()=>this.tryPattern(s.id,s.pattern,s.format)}>${t("try_pattern")}</button>
            <button class="link danger" @click=${()=>this.change(t=>t.buttons.splice(i,1))}>${t("remove")}</button>
          </div>
          ${o?I`<div class="note mono ${o.ok?"ok":"bad"}" style="white-space:pre-wrap">${o.text}</div>`:F}
        </div>`})}
      <button @click=${()=>this.change(t=>t.buttons.push({id:mt(),name:"",pattern:"",format:"hex",debounce_ms:300,target:"",action:"",value:null}))}>${t("add_button")}</button>
    </div>`}renderChoices(){const t=this.t;return this.spec.options?I`<div class="card">
      <h2>${t("sec_options")}</h2>
      <div class="hint">${t("options_hint")}</div>
      ${this.draft.options.map((e,s)=>I`<div class="row" style="margin-bottom:6px">
          <input class="grow" placeholder=${t("option_name")} .value=${e.name} @input=${t=>this.change(e=>e.options[s].name=Ot(t))} />
          ${this.commandSelect(e.command,t=>this.change(e=>e.options[s].command=t))}
          <button class="link danger" @click=${()=>this.change(t=>t.options.splice(s,1))}>${t("remove")}</button>
        </div>`)}
      <button @click=${()=>this.change(t=>t.options.push({name:"",command:""}))}>${t("add_option")}</button>
    </div>`:F}renderRanges(){const t=this.t,e=this.spec.actions.filter(t=>t in this.valueActions).map(t=>this.valueActions[t]);return e.length?I`<div class="card">
      <h2>${t("sec_ranges")}</h2>
      <div class="hint">${t("ranges_hint")}</div>
      ${e.map(e=>{const s=this.draft.ranges[e]??[0,100],i=(t,s)=>this.change(i=>{const o=[...i.ranges[e]??[0,100]];o[t]=s,i.ranges[e]=o});return I`<div class="row" style="margin-bottom:6px">
          <span class="small">${this.label("field_",e)}</span>
          <span class="muted">${t("range_at0")}</span>
          <input class="small" type="number" .value=${String(s[0])} @input=${t=>i(0,Tt(t))} />
          <span class="muted">${t("range_at100")}</span>
          <input class="small" type="number" .value=${String(s[1])} @input=${t=>i(1,Tt(t,100))} />
        </div>`})}
    </div>`:F}renderRules(){const t=this.t,e=this.spec.fields;return e.length?I`<div class="card">
      <h2>${t("sec_rules")}</h2>
      <div class="hint">${t("rules_hint")}</div>
      ${this.draft.rules.map((s,i)=>{const o=this.tried[s.id],a=t=>this.change(e=>t(e.rules[i]));return I`<div class="item">
          <div class="row">
            <input class="wide mono" placeholder=${t("pattern")} .value=${s.pattern} @input=${t=>a(e=>e.pattern=Ot(t))} />
            ${this.formatSelect(s.format,t=>a(e=>e.format=t))}
          </div>
          <div class="row">
            <span class="muted">${t("field")}</span>
            <select @change=${t=>a(e=>e.field=Ot(t))}>
              ${e.map(t=>I`<option value=${t} ?selected=${t===s.field}>${this.label("field_",t)}</option>`)}
            </select>
            <span class="muted">${t("value")}</span>
            <input class="small mono" placeholder=${t("value_hint")} title=${t("value_hint")} .value=${s.value} @input=${t=>a(e=>e.value=Ot(t))} />
            <span class="grow"></span>
            <button class="link" @click=${()=>this.tryPattern(s.id,s.pattern,s.format)}>${t("try_pattern")}</button>
            <button class="link danger" @click=${()=>this.change(t=>t.rules.splice(i,1))}>${t("remove")}</button>
          </div>
          ${o?I`<div class="note mono ${o.ok?"ok":"bad"}" style="white-space:pre-wrap">${o.text}</div>`:F}
        </div>`})}
      <button @click=${()=>this.change(t=>t.rules.push({id:mt(),pattern:"",format:"hex",field:e[0],value:""}))}>${t("add_rule")}</button>
    </div>`:F}renderSensors(){const t=this.t;return I`<div class="card">
      <h2>${t("sec_sensors")}</h2>
      <div class="hint">${t("sensors_hint")}</div>
      ${this.draft.sensors.map((e,s)=>{const i=this.tried[e.id],o=t=>this.change(e=>t(e.sensors[s]));return I`<div class="item">
          <div class="row">
            <input class="small" placeholder=${t("name")} .value=${e.name} @input=${t=>o(e=>e.name=Ot(t))} />
            <input class="wide mono" placeholder=${t("pattern")} .value=${e.pattern} @input=${t=>o(e=>e.pattern=Ot(t))} />
            ${this.formatSelect(e.format,t=>o(e=>e.format=t))}
          </div>
          <div class="row muted">
            <span>${t("capture")}</span>
            <input class="small mono" .value=${e.capture} @input=${t=>o(e=>e.capture=Ot(t))} />
            <span>${t("scale")}</span>
            <input class="tiny" type="number" step="any" .value=${String(e.scale)} @input=${t=>o(e=>e.scale=Tt(t,1))} />
            <span>${t("offset")}</span>
            <input class="tiny" type="number" step="any" .value=${String(e.offset)} @input=${t=>o(e=>e.offset=Tt(t))} />
            <span>${t("unit")}</span>
            <input class="tiny" .value=${e.unit} @input=${t=>o(e=>e.unit=Ot(t))} />
            <span>${t("device_class")}</span>
            <input class="small" placeholder="voltage" .value=${e.device_class} @input=${t=>o(e=>e.device_class=Ot(t))} />
            <span>${t("precision")}</span>
            <input class="tiny" type="number" min="0" max="6" .value=${null===e.precision?"":String(e.precision)}
              @input=${t=>o(e=>e.precision=""===Ot(t)?null:Math.max(0,Math.round(Tt(t))))} />
            <span class="grow"></span>
            <button class="link" @click=${()=>this.tryPattern(e.id,e.pattern,e.format)}>${t("try_pattern")}</button>
            <button class="link danger" @click=${()=>this.change(t=>t.sensors.splice(s,1))}>${t("remove")}</button>
          </div>
          ${i?I`<div class="note mono ${i.ok?"ok":"bad"}" style="white-space:pre-wrap">${i.text}</div>`:F}
        </div>`})}
      <button @click=${()=>this.change(t=>t.sensors.push({id:mt(),name:"",pattern:"",format:"hex",capture:"value",scale:1,offset:0,unit:"",device_class:"",precision:null}))}>${t("add_sensor")}</button>
    </div>`}renderPoll(){const t=this.t;return I`<div class="card">
      <h2>${t("sec_poll")}</h2>
      <div class="hint">${t("poll_hint")}</div>
      <div class="row">
        <span class="muted">${t("poll_command")}</span>
        ${this.commandSelect(this.draft.poll_command,t=>this.change(e=>{e.poll_command=t,t&&!e.poll_interval&&(e.poll_interval=30)}),t("no_poll"))}
        ${this.draft.poll_command?I`<span class="muted">${t("poll_interval")}</span>
              <input class="small" type="number" min="1" max="86400" .value=${String(this.draft.poll_interval)}
                @input=${t=>this.change(e=>e.poll_interval=Math.max(1,Math.round(Tt(t,30))))} />`:F}
      </div>
    </div>`}render(){if(!this.draft)return F;const t=this.t;return I`
      ${this.renderBasic()} ${this.renderParams()} ${this.renderButtons()} ${this.renderCommands()} ${this.renderActions()}
      ${this.renderChoices()} ${this.renderRanges()} ${this.renderRules()} ${this.renderSensors()} ${this.renderPoll()}
      <div class="footer">
        <button @click=${this.leave}>${t("back")}</button>
        ${this.draft.id?I`<button class="danger" @click=${this.removeDevice}>${t("delete_device")}</button>`:F}
        <span class="grow note ${this.status?this.status.ok?"ok":"bad":""}" style="white-space:pre-wrap"
          >${this.status?.text??(this.dirty?t("unsaved"):"")}</span
        >
        <button class="primary" ?disabled=${this.busy} @click=${this.save}>${t("save")}</button>
      </div>
    `}}Rt.styles=[Mt,n`
      .form {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 10px 12px;
      }
      label {
        display: grid;
        gap: 4px;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }
      label > input,
      label > select {
        font-size: 1.1em;
      }
      .hint {
        margin: -6px 0 10px;
        color: var(--secondary-text-color);
        font-size: 0.85em;
        white-space: pre-wrap;
      }
      .item {
        border-top: 1px solid var(--divider-color, #eee);
        padding: 10px 0;
        display: grid;
        gap: 6px;
      }
      .item .row > input,
      .item .row > select {
        min-width: 0;
      }
      .wide {
        flex: 1 1 260px;
      }
      .small {
        width: 6.5em;
      }
      .tiny {
        width: 4.5em;
      }
      .note {
        font-size: 0.85em;
      }
      .note.ok {
        color: var(--success-color, #43a047);
      }
      .note.bad {
        color: var(--error-color, #db4437);
      }
      .footer {
        position: sticky;
        bottom: 0;
        z-index: 2;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        padding: 12px 16px;
        margin: 0 -16px -16px;
        background: var(--card-background-color, #fff);
        border-top: 1px solid var(--divider-color, #e0e0e0);
      }
      .actions-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 8px 12px;
      }
    `],t([pt({attribute:!1})],Rt.prototype,"device",void 0),t([pt({attribute:!1})],Rt.prototype,"devices",void 0),t([pt({attribute:!1})],Rt.prototype,"types",void 0),t([pt({attribute:!1})],Rt.prototype,"valueActions",void 0),t([pt({attribute:!1})],Rt.prototype,"ports",void 0),t([pt({attribute:!1})],Rt.prototype,"state",void 0),t([pt({attribute:!1})],Rt.prototype,"t",void 0),t([pt({attribute:!1})],Rt.prototype,"api",void 0),t([pt({attribute:!1})],Rt.prototype,"portName",void 0),t([ht()],Rt.prototype,"draft",void 0),t([ht()],Rt.prototype,"params",void 0),t([ht()],Rt.prototype,"dirty",void 0),t([ht()],Rt.prototype,"status",void 0),t([ht()],Rt.prototype,"busy",void 0),t([ht()],Rt.prototype,"previews",void 0),t([ht()],Rt.prototype,"tried",void 0),t([ht()],Rt.prototype,"listening",void 0),vt("woow-serial-device-editor",Rt);class Ht extends rt{constructor(){super(...arguments),this.devices=[],this.states={},this.types={},this.valueActions={},this.ports=[],this.now=0,this.open=null,this.editing=null}willUpdate(t){t.has("open")&&this.open&&(this.editing=this.open,this.dispatchEvent(new CustomEvent("opened",{bubbles:!0,composed:!0})))}typeLabel(t){const e=`type_${t}`;return Ct(e)?this.t(e):t}close(){this.editing=null}render(){const t=this.t;if(this.editing){const t=this.editing.id?this.devices.find(t=>t.id===this.editing?.id)??this.editing:this.editing;return I`<woow-serial-device-editor
        .device=${t}
        .devices=${this.devices}
        .types=${this.types}
        .valueActions=${this.valueActions}
        .ports=${this.ports}
        .state=${this.states[t.id]}
        .t=${this.t}
        .api=${this.api}
        .portName=${this.portName}
        @close=${this.close}
      ></woow-serial-device-editor>`}const e=[...this.devices].sort((t,e)=>t.name.localeCompare(e.name));return I`<div class="card">
      <div class="row" style="margin-bottom:12px">
        <h2 class="grow" style="margin:0">${t("tab_devices")}</h2>
        <button class="primary" ?disabled=${!this.ports.length} @click=${()=>this.editing=$t(this.ports[0]?.id??"")}>
          ${t("add_device")}
        </button>
      </div>
      ${0===e.length?I`<div class="empty">${t("devices_empty")}</div>`:I`<div class="grid">
            ${e.map(e=>{const s=gt(e,this.states[e.id],t);return I`<div class="dev" @click=${()=>this.editing=e}>
                <div class="row"><b class="grow">${e.name}</b><span class="chip">${this.typeLabel(e.type)}</span></div>
                <div class="muted">${this.portName(e.port_id)}${e.manufacturer||e.model?` · ${[e.manufacturer,e.model].filter(Boolean).join(" ")}`:""}</div>
                ${s.length?I`<div class="state">${s.map(t=>I`<span class="chip info">${t}</span>`)}</div>`:F}
                <div class="muted">${t("entities_count",{n:e.entities?.length??0})}</div>
              </div>`})}
          </div>`}
    </div>`}}Ht.styles=[Mt,n`
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 12px;
      }
      .dev {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 10px;
        padding: 12px;
        display: grid;
        gap: 6px;
        cursor: pointer;
        background: var(--card-background-color, #fff);
      }
      .dev:hover {
        border-color: var(--primary-color);
      }
      .state {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
      }
    `],t([pt({attribute:!1})],Ht.prototype,"devices",void 0),t([pt({attribute:!1})],Ht.prototype,"states",void 0),t([pt({attribute:!1})],Ht.prototype,"types",void 0),t([pt({attribute:!1})],Ht.prototype,"valueActions",void 0),t([pt({attribute:!1})],Ht.prototype,"ports",void 0),t([pt({attribute:!1})],Ht.prototype,"now",void 0),t([pt({attribute:!1})],Ht.prototype,"t",void 0),t([pt({attribute:!1})],Ht.prototype,"api",void 0),t([pt({attribute:!1})],Ht.prototype,"portName",void 0),t([pt({attribute:!1})],Ht.prototype,"open",void 0),t([ht()],Ht.prototype,"editing",void 0),vt("woow-serial-devices",Ht);const jt=t=>t.target.value,Ut=new Set(["crc16_modbus","crc16_ccitt","crc16_xmodem","sum16"]);class Dt extends rt{constructor(){super(...arguments),this.ports=[],this.groups=[],this.rows=[],this.groupPrefix={},this.now=0,this.portFilter="",this.showHidden=!1,this.open=new Set,this.status=""}toggle(t){const e=new Set(this.open);e.has(t)?e.delete(t):e.add(t),this.open=e}flash(t){this.status=t,window.setTimeout(()=>{this.status===t&&(this.status="")},3e3)}async run(t){try{await t()}catch(t){this.flash(this.t("error",{msg:_t(t)}))}}renameGroup(t){const e=window.prompt(this.t("alias_prompt"),t.alias);null!==e&&this.run(()=>this.api.updateGroup(t.id,{alias:e.trim()}))}renameRow(t){const e=window.prompt(this.t("alias_prompt"),t.alias);null!==e&&this.run(()=>this.api.updateRow(t.id,e.trim()))}deleteGroup(t){window.confirm(this.t("delete_group_confirm"))&&this.run(()=>this.api.deleteGroup(t.id))}resend(t){this.run(async()=>{const e=await this.api.send(t.port_id,{hex:t.hex});this.flash(this.t("sent_x",{x:e.sent}))})}applyPrefix(t,e){window.confirm(this.t("prefix_confirm"))?this.run(async()=>{await this.api.setPrefix(t,e),this.dispatchEvent(new CustomEvent("prefix-changed",{detail:{portId:t,length:e},bubbles:!0,composed:!0}))}):this.requestUpdate()}clearPort(t){window.confirm(this.t("clear_port_confirm",{port:this.portName(t)}))&&this.run(()=>this.api.clearCatalog(t))}bytes(t,e){const s=t.hex.split(" "),i="text"===e.key||"*"===e.key?0:e.key.split(" ").length,o=e.checksum&&t.checks.includes(e.checksum)?Ut.has(e.checksum.split("@")[0])?2:1:0,a=o&&s.length>i+o?o:0;return I`<span class="pre">${s.slice(0,i).join(" ")}</span> ${s.slice(i,s.length-a).join(" ")}
      <span class="ck">${s.slice(s.length-a).join(" ")}</span>`}renderGroup(t,e){const s=this.t,i=this.open.has(t.id),o="text"===t.key?s("text_group"):"*"===t.key?s("all_bytes"):t.key;return I`<div class="group ${t.hidden?"is-hidden":""}">
      <div class="ghead" @click=${()=>this.toggle(t.id)}>
        <span class="caret">${i?"▾":"▸"}</span>
        <div class="grow">
          <div class="row">
            <b class=${t.alias?"":"mono"}>${t.alias||o}</b>
            ${t.alias?I`<span class="muted mono">${o}</span>`:F}
            ${t.checksum?I`<span class="chip ok">${s("checksum_is",{name:St(t.checksum,s)})}</span>`:F}
            ${t.hidden?I`<span class="chip">${s("hidden")}</span>`:F}
          </div>
          <div class="muted">
            ${this.portName(t.port_id)} · ${s("frames_count",{n:t.count})} · ${s("variants",{n:t.rows})} ·
            ${Et(t.last_seen,s)}${t.rate?` · ${s("per_second",{n:t.rate})}`:""}
          </div>
        </div>
        <div class="actions" @click=${t=>t.stopPropagation()}>
          <button class="link" @click=${()=>this.renameGroup(t)}>${s("rename")}</button>
          <button class="link" @click=${()=>this.run(()=>this.api.updateGroup(t.id,{hidden:!t.hidden}))}>
            ${t.hidden?s("unhide"):s("hide")}
          </button>
          <button class="link danger" @click=${()=>this.deleteGroup(t)}>${s("delete")}</button>
        </div>
      </div>
      ${i?I`<div class="rows">
            ${e.map(e=>I`<div class="rrow">
                <div class="grow">
                  <div class="mono">${this.bytes(e,t)}</div>
                  ${e.text?I`<div class="muted mono">"${e.text}"</div>`:F}
                  <div class="muted">
                    ${e.alias?I`<b>${e.alias}</b> · `:F}${s("times",{n:e.count})} · ${Et(e.last_seen,s)}
                  </div>
                </div>
                <div class="actions">
                  <button class="link" @click=${()=>this.dispatchEvent(new CustomEvent("add-to-device",{detail:e,bubbles:!0,composed:!0}))}>
                    ${s("add_to_device")}
                  </button>
                  <button class="link" @click=${()=>this.dispatchEvent(new CustomEvent("make-button",{detail:e,bubbles:!0,composed:!0}))}>
                    ${s("make_button")}
                  </button>
                  <button class="link" @click=${()=>this.resend(e)}>${s("send_again")}</button>
                  <button class="link" @click=${()=>this.renameRow(e)}>${s("rename")}</button>
                  <button class="link" @click=${()=>{!function(t){if(navigator.clipboard&&window.isSecureContext)return void navigator.clipboard.writeText(t);const e=document.createElement("textarea");e.value=t,e.style.position="fixed",e.style.opacity="0",document.body.appendChild(e),e.select(),document.execCommand("copy"),e.remove()}(e.hex),this.flash(s("copied"))}}>${s("copy")}</button>
                  <button class="link danger" @click=${()=>this.run(()=>this.api.deleteRow(e.id))}>${s("delete")}</button>
                </div>
              </div>`)}
          </div>`:F}
    </div>`}render(){const t=this.t,e=new Map;for(const t of this.rows){const s=e.get(t.group_id);s?s.push(t):e.set(t.group_id,[t])}for(const t of e.values())t.sort((t,e)=>e.last_seen-t.last_seen);const s=this.groups.filter(t=>(!this.portFilter||t.port_id===this.portFilter)&&(this.showHidden||!t.hidden)).sort((t,e)=>t.order-e.order||e.last_seen-t.last_seen),i=this.ports.find(t=>t.id===this.portFilter);return I`
      <div class="card toolbar row">
        <select @change=${t=>this.portFilter=jt(t)}>
          <option value="">${t("all_ports")}</option>
          ${this.ports.map(t=>I`<option value=${t.id} ?selected=${t.id===this.portFilter}>${t.name}</option>`)}
        </select>
        <label class="row muted">
          <input type="checkbox" .checked=${this.showHidden} @change=${t=>this.showHidden=t.target.checked} />
          ${t("show_hidden")}
        </label>
        <span class="grow muted">${this.status}</span>
        ${i?I`<span class="muted">${t("group_by")}</span>
              <input type="number" min="0" max="8" style="width:4em" .value=${String(this.groupPrefix[i.id]??2)}
                @change=${t=>this.applyPrefix(i.id,Math.min(8,Math.max(0,Number(jt(t))||0)))} />
              <span class="muted">${t("bytes")}</span>`:F}
        ${i?I`<button @click=${()=>this.clearPort(i.id)}>${t("clear")}</button>`:F}
      </div>
      <div class="card">
        ${s.length?s.map(t=>this.renderGroup(t,e.get(t.id)??[])):I`<div class="empty">${t("monitor_empty")}</div>`}
      </div>
    `}}Dt.styles=[Mt,n`
      .toolbar {
        position: sticky;
        top: 0;
        z-index: 1;
      }
      .group {
        border-top: 1px solid var(--divider-color, #eee);
      }
      .group:first-child {
        border-top: none;
      }
      .group.is-hidden {
        opacity: 0.6;
      }
      .ghead {
        display: flex;
        gap: 8px;
        align-items: flex-start;
        padding: 10px 0;
        cursor: pointer;
      }
      .caret {
        width: 1em;
        color: var(--secondary-text-color);
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 2px;
      }
      .rows {
        margin: 0 0 10px 1.5em;
      }
      .rrow {
        display: flex;
        gap: 8px;
        align-items: flex-start;
        padding: 6px 0;
        border-top: 1px dashed var(--divider-color, #eee);
      }
      .pre {
        font-weight: 600;
      }
      .ck {
        color: var(--success-color, #43a047);
        font-weight: 600;
      }
    `],t([pt({attribute:!1})],Dt.prototype,"ports",void 0),t([pt({attribute:!1})],Dt.prototype,"groups",void 0),t([pt({attribute:!1})],Dt.prototype,"rows",void 0),t([pt({attribute:!1})],Dt.prototype,"groupPrefix",void 0),t([pt({attribute:!1})],Dt.prototype,"now",void 0),t([pt({attribute:!1})],Dt.prototype,"t",void 0),t([pt({attribute:!1})],Dt.prototype,"api",void 0),t([pt({attribute:!1})],Dt.prototype,"portName",void 0),t([ht()],Dt.prototype,"portFilter",void 0),t([ht()],Dt.prototype,"showHidden",void 0),t([ht()],Dt.prototype,"open",void 0),t([ht()],Dt.prototype,"status",void 0),vt("woow-serial-monitor",Dt);const Wt=["crc16_modbus","crc16_ccitt","crc16_xmodem","sum16","crc8","crc8_maxim","xor8","sum8","sum8_neg"],Lt=t=>t.target.value;class zt extends rt{constructor(){super(...arguments),this.ports=[],this.live=[],this.dropped=0,this.paused=!1,this.deviceName=()=>{},this.portId="",this.mode="hex",this.payload="",this.algorithm="",this.start=0,this.waitMs=500,this.busy=!1,this.result=null,this.liveFilter=""}get selected(){return this.ports.find(t=>t.id===this.portId)??this.ports[0]}control(t){this.dispatchEvent(new CustomEvent("live-control",{detail:t,bubbles:!0,composed:!0}))}async send(){const t=this.selected;if(!t||!this.payload.trim()||this.busy)return;const e=this.t;this.busy=!0,this.result=null;try{let s;if("text"===this.mode)s={text:this.payload};else{let t=this.payload;this.algorithm&&(t=(await this.api.checksum(t,this.algorithm,this.start)).frame??t),s={hex:t}}const i=await this.api.send(t.id,{...s,wait_ms:this.waitMs});let o=e("sent_x",{x:i.sent});i.reply?o+=`   ${e("reply_x",{x:i.reply})}`:i.timeout&&(o+=`   ${e("timeout")}`),this.result={ok:!i.timeout,text:o}}catch(t){this.result={ok:!1,text:e("error",{msg:_t(t)})}}finally{this.busy=!1}}renderPort(t){const e=this.t,s="external"===t.kind?e("kind_external"):e("kind_serial");return I`<div class="port">
      <div class="row">
        <span class="dot ${t.available?"on":""}" title=${t.available?e("online"):e("offline")}></span>
        <b class="grow">${t.name}</b>
        <span class="chip ${"external"===t.kind?"info":""}">${s}</span>
      </div>
      <div class="muted ${"external"===t.kind?"":"mono"}" title=${"external"===t.kind?`${t.tx_entity} / ${t.rx_entity}`:t.model}>
        ${"external"===t.kind?t.model:t.port}
      </div>
      <div class="muted">${t.settings||"—"}</div>
      <div class="row muted">
        <span>${e("frames_in",{n:t.rx_frames??0})}</span>
        <span>${e("frames_out",{n:t.tx_frames??0})}</span>
        ${t.errors?I`<span class="chip bad">${e("errors",{n:t.errors})}</span>`:F}
      </div>
    </div>`}renderSend(){const t=this.t,e=this.selected,s="hex"===this.mode?t("ph_hex"):t("ph_text");return I`<div class="card">
      <h2>${t("send_title")}</h2>
      <div class="row send-row">
        <select @change=${t=>this.portId=Lt(t)} aria-label=${t("port")}>
          ${this.ports.map(t=>I`<option value=${t.id} ?selected=${t.id===e?.id}>${t.name}</option>`)}
        </select>
        <select @change=${t=>this.mode=Lt(t)}>
          <option value="hex" ?selected=${"hex"===this.mode}>${t("mode_hex")}</option>
          <option value="text" ?selected=${"text"===this.mode}>${t("mode_text")}</option>
        </select>
        <input
          class="grow mono"
          .value=${this.payload}
          placeholder=${s}
          @input=${t=>this.payload=Lt(t)}
          @keydown=${t=>"Enter"===t.key&&this.send()}
        />
      </div>
      <div class="row send-row">
        ${"hex"===this.mode?I`<span class="muted">${t("append_checksum")}</span>
              <select @change=${t=>this.algorithm=Lt(t)}>
                <option value="">${t("none")}</option>
                ${Wt.map(e=>I`<option value=${e} ?selected=${e===this.algorithm}>${St(e,t)}</option>`)}
              </select>
              ${this.algorithm?I`<span class="muted">${t("start_at")}</span>
                    <input type="number" min="1" max="17" style="width:4em" .value=${String(this.start+1)}
                      @input=${t=>this.start=Math.max(0,(Number(Lt(t))||1)-1)} />`:F}`:F}
        <span class="muted">${t("wait_ms")}</span>
        <input type="number" min="0" max="60000" step="100" style="width:6em" .value=${String(this.waitMs)}
          @input=${t=>this.waitMs=Math.max(0,Number(Lt(t))||0)} />
        <span class="grow"></span>
        <button class="primary" ?disabled=${this.busy||!e} @click=${()=>this.send()}>${t("send")}</button>
      </div>
      ${this.result?I`<div class="result mono ${this.result.ok?"":"bad"}">${this.result.text}</div>`:F}
    </div>`}renderLive(){const t=this.t,e=this.liveFilter?this.live.filter(t=>t.port===this.liveFilter):this.live;return I`<div class="card">
      <div class="row">
        <h2 class="grow">${t("live_title")}</h2>
        <select @change=${t=>this.liveFilter=Lt(t)}>
          <option value="">${t("all_ports")}</option>
          ${this.ports.map(t=>I`<option value=${t.id}>${t.name}</option>`)}
        </select>
        <button @click=${()=>this.control(this.paused?"resume":"pause")}>${this.paused?t("resume"):t("pause")}</button>
        <button @click=${()=>this.control("clear")}>${t("clear")}</button>
      </div>
      ${this.dropped?I`<div class="chip warn">${t("dropped",{n:this.dropped})}</div>`:F}
      ${0===e.length?I`<div class="empty">${t("live_empty")}</div>`:I`<div class="live">
            ${e.map(e=>I`<div class="lrow">
                <span class="muted mono">${function(t){const e=new Date(1e3*t),s=(t,e=2)=>String(t).padStart(e,"0");return`${s(e.getHours())}:${s(e.getMinutes())}:${s(e.getSeconds())}.${s(e.getMilliseconds(),3)}`}(e.t)}</span>
                <span class=${e.dir}>${"rx"===e.dir?"⬇":"⬆"}</span>
                <span class="pname">${this.portName(e.port)}</span>
                <span class="mono grow">${e.hex}${e.text?I` <span class="muted">"${e.text}"</span>`:F}</span>
                ${"tx"===e.dir?I`<span class="chip info">${Pt(e.origin,t,this.deviceName)}</span>`:F}
                ${e.echo?I`<span class="chip">${t("echo")}</span>`:F}
              </div>`)}
          </div>`}
    </div>`}render(){const t=this.t;return I`
      <div class="card">
        ${this.ports.length?I`<div class="ports">${this.ports.map(t=>this.renderPort(t))}</div>`:I`<div class="empty">${t("no_ports")}</div>`}
      </div>
      ${this.ports.length?this.renderSend():F} ${this.renderLive()}
    `}}zt.styles=[Mt,n`
      .ports {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
        gap: 12px;
      }
      .port {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 10px;
        padding: 10px 12px;
        display: grid;
        gap: 4px;
      }
      .dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--error-color, #db4437);
        flex: none;
      }
      .dot.on {
        background: var(--success-color, #43a047);
      }
      .result {
        margin-top: 10px;
        padding: 8px 10px;
        border-radius: 8px;
        background: rgba(67, 160, 71, 0.12);
      }
      .result.bad {
        background: rgba(219, 68, 55, 0.12);
      }
      .live {
        max-height: 60vh;
        overflow: auto;
        margin-top: 8px;
      }
      .lrow {
        display: flex;
        align-items: baseline;
        gap: 8px;
        padding: 4px 0;
        border-bottom: 1px solid var(--divider-color, #eee);
      }
      .pname {
        flex: none;
        max-width: 10em;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .send-row + .send-row {
        margin-top: 8px;
      }
    `],t([pt({attribute:!1})],zt.prototype,"ports",void 0),t([pt({attribute:!1})],zt.prototype,"live",void 0),t([pt({attribute:!1})],zt.prototype,"dropped",void 0),t([pt({attribute:!1})],zt.prototype,"paused",void 0),t([pt({attribute:!1})],zt.prototype,"t",void 0),t([pt({attribute:!1})],zt.prototype,"api",void 0),t([pt({attribute:!1})],zt.prototype,"portName",void 0),t([pt({attribute:!1})],zt.prototype,"deviceName",void 0),t([ht()],zt.prototype,"portId",void 0),t([ht()],zt.prototype,"mode",void 0),t([ht()],zt.prototype,"payload",void 0),t([ht()],zt.prototype,"algorithm",void 0),t([ht()],zt.prototype,"start",void 0),t([ht()],zt.prototype,"waitMs",void 0),t([ht()],zt.prototype,"busy",void 0),t([ht()],zt.prototype,"result",void 0),t([ht()],zt.prototype,"liveFilter",void 0),vt("woow-serial-overview",zt);class Bt extends rt{constructor(){super(...arguments),this.sent=[],this.ports=[],this.now=0,this.deviceName=()=>{},this.status=""}async run(t){try{await t()}catch(t){this.status=this.t("error",{msg:_t(t)})}}resend(t){this.run(async()=>{const e=await this.api.send(t.port_id,{hex:t.hex});this.status=this.t("sent_x",{x:e.sent})})}clearAll(){window.confirm(this.t("clear_all_confirm"))&&this.run(()=>this.api.deleteSent())}render(){const t=this.t,e=[...this.sent].sort((t,e)=>e.last_sent-t.last_sent);return I`<div class="card">
      <div class="row">
        <h2 class="grow">${t("tab_sendlog")}</h2>
        <span class="muted">${this.status}</span>
        ${e.length?I`<button @click=${()=>this.clearAll()}>${t("clear_all")}</button>`:F}
      </div>
      ${0===e.length?I`<div class="empty">${t("sendlog_empty")}</div>`:e.map(e=>{const s=Object.keys(e.heard_by);return I`<div class="srow">
              <div class="grow">
                <div class="row">
                  <span class="mono">${e.hex}</span>
                  ${e.text?I`<span class="muted mono">"${e.text}"</span>`:F}
                </div>
                <div class="row muted">
                  <span>${this.portName(e.port_id)}</span>
                  <span>${t("times",{n:e.count})}</span>
                  <span>${Et(e.last_sent,t)}</span>
                  <span class="chip info">${Pt(e.origin,t,this.deviceName)}</span>
                  ${e.replies?I`<span class="chip ok mono">${t("reply_ms",{x:e.reply??"",ms:e.reply_ms??0})}</span>`:I`<span class="chip">${t("no_reply")}</span>`}
                  ${s.length?I`<span class="chip ok">${t("heard_by",{ports:s.map(t=>this.portName(t)).join("、")})}</span>`:F}
                </div>
              </div>
              <div class="actions">
                <button class="link" @click=${()=>this.resend(e)}>${t("send_again")}</button>
                <button class="link danger" @click=${()=>this.run(()=>this.api.deleteSent(e.id))}>${t("delete")}</button>
              </div>
            </div>`})}
    </div>`}}Bt.styles=[Mt,n`
      .srow {
        display: flex;
        gap: 8px;
        align-items: flex-start;
        padding: 10px 0;
        border-top: 1px solid var(--divider-color, #eee);
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
      }
    `],t([pt({attribute:!1})],Bt.prototype,"sent",void 0),t([pt({attribute:!1})],Bt.prototype,"ports",void 0),t([pt({attribute:!1})],Bt.prototype,"now",void 0),t([pt({attribute:!1})],Bt.prototype,"t",void 0),t([pt({attribute:!1})],Bt.prototype,"api",void 0),t([pt({attribute:!1})],Bt.prototype,"portName",void 0),t([pt({attribute:!1})],Bt.prototype,"deviceName",void 0),t([ht()],Bt.prototype,"status",void 0),vt("woow-serial-sendlog",Bt);const It=["overview","devices","monitor","sendlog"],Vt={serial:0,external:1},Ft="__new__";class Xt extends rt{constructor(){super(...arguments),this.narrow=!1,this.tab="overview",this.ports={},this.groups={},this.rows={},this.groupPrefix={},this.sent={},this.devices={},this.deviceStates={},this.deviceTypes={},this.valueActions={},this.openDevice=null,this.live=[],this.dropped=0,this.paused=!1,this.loaded=!1,this.error="",this.now=Date.now(),this.addRow=null,this.addMode="command",this.addTarget=Ft,this.addName="",this.addNote="",this.t=kt("en"),this.api=new ut(()=>this._hass),this.connecting=!1,this.portName=t=>this.ports[t]?.name??"?",this.deviceName=t=>this.devices[t]?.name}set hass(t){const e=!this._hass;this._hass=t,e&&(this.t=kt(t.locale?.language??t.language??"en"),this.isConnected&&this.connect(),this.requestUpdate())}get hass(){return this._hass}connectedCallback(){super.connectedCallback(),this._hass&&!this.unsubscribe&&this.connect(),this.ticker=window.setInterval(()=>this.now=Date.now(),5e3)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this.ticker),this.unsubscribe?.(),this.unsubscribe=void 0}async connect(){if(!this.connecting&&!this.unsubscribe){this.connecting=!0;try{this.unsubscribe=await this.api.subscribe(t=>this.onEvent(t));const t=await this.api.snapshot();this.ports=Object.fromEntries(t.ports.map(t=>[t.id,t])),this.groups=Object.fromEntries(t.catalog.groups.map(t=>[t.id,t])),this.rows=Object.fromEntries(t.catalog.rows.map(t=>[t.id,t])),this.groupPrefix=t.catalog.prefix,this.sent=Object.fromEntries(t.mirror.rows.map(t=>[t.id,t])),this.devices=Object.fromEntries(t.devices.devices.map(t=>[t.id,t])),this.deviceStates=t.devices.states,this.deviceTypes=t.devices.types,this.valueActions=t.devices.value_actions,this.loaded=!0,this.error=""}catch(t){this.error=_t(t)}finally{this.connecting=!1}}}onEvent(t){switch(t.kind){case"frames":this.paused||(this.live=[...t.frames.reverse(),...this.live].slice(0,300),this.dropped+=t.dropped);break;case"ports":{const e={...this.ports};for(const s of t.ports)e[s.id]=s;for(const s of t.removed)delete e[s];this.ports=e;break}case"catalog":{const e={...this.groups},s={...this.rows};for(const s of t.groups)e[s.id]=s;for(const e of t.rows)s[e.id]=e;for(const i of t.removed)delete e[i],delete s[i];this.groups=e,this.rows=s;break}case"mirror":{const e={...this.sent};for(const s of t.rows)e[s.id]=s;for(const s of t.removed)delete e[s];this.sent=e;break}case"devices":{const e={...this.devices};for(const s of t.devices)e[s.id]=s;for(const s of t.removed)delete e[s];this.devices=e;break}case"device_state":this.deviceStates={...this.deviceStates,...t.states}}}onLiveControl(t){"clear"===t.detail?(this.live=[],this.dropped=0):this.paused="pause"===t.detail}get portList(){return Object.values(this.ports).sort((t,e)=>(Vt[t.kind]??9)-(Vt[e.kind]??9)||t.name.localeCompare(e.name))}toggleMenu(){this.dispatchEvent(new Event("hass-toggle-menu",{bubbles:!0,composed:!0}))}candidates(t,e){return Object.values(this.devices).filter(s=>s.port_id===t.port_id&&("button"===e?"keypad"===s.type:"keypad"!==s.type))}startAdd(t,e="command"){const s=this.candidates(t,e);this.addMode=e,this.addRow=t,this.addTarget=s[0]?.id??Ft,this.addName=t.alias||"",this.addNote=""}async confirmAdd(){const t=this.addRow;if(!t)return;const e=this.t,s=this.addName.trim()||t.hex.slice(0,20),i="button"===this.addMode,o={id:mt(),name:s,repeat:1,gap_ms:100,wait_ms:0,...yt(t)},a={id:mt(),name:s,debounce_ms:300,target:"",action:"",value:null,...ft(t)};if(this.addTarget===Ft)return this.openDevice=i?{...$t(t.port_id),type:"keypad",buttons:[a]}:{...$t(t.port_id),type:"other",commands:[o]},this.addRow=null,void(this.tab="devices");const n=this.devices[this.addTarget];if(!n)return;const r=i?{...structuredClone(n),buttons:[...n.buttons,a]}:{...structuredClone(n),commands:[...n.commands,o]};delete r.entities,delete r.bindable;try{const t=await this.api.saveDevice(r);if(t.error)return void(this.addNote=Nt(t.error,e));this.addRow=null}catch(t){this.addNote=e("error",{msg:_t(t)})}}renderAddDialog(){const t=this.addRow;if(!t)return F;const e=this.t,s="button"===this.addMode,i=this.candidates(t,this.addMode);return I`<div class="scrim" @click=${t=>t.target===t.currentTarget&&(this.addRow=null)}>
      <div class="dialog">
        <h2>${e(s?"make_button":"add_to_device")}</h2>
        <div class="mono">${t.hex}${t.text?I` <span class="muted">"${t.text}"</span>`:F}</div>
        <label
          >${e(s?"choose_keypad":"choose_device")}
          <select @change=${t=>this.addTarget=t.target.value}>
            ${i.map(t=>I`<option value=${t.id} ?selected=${t.id===this.addTarget}>${t.name}</option>`)}
            <option value=${Ft} ?selected=${this.addTarget===Ft}>${e(s?"new_keypad":"new_device")}</option>
          </select>
        </label>
        <label
          >${e(s?"button_name":"command_name")}
          <input .value=${this.addName} @input=${t=>this.addName=t.target.value}
            @keydown=${t=>"Enter"===t.key&&this.confirmAdd()} />
        </label>
        ${this.addNote?I`<div class="chip bad" style="white-space:normal">${this.addNote}</div>`:F}
        <div class="row">
          <span class="grow"></span>
          <button @click=${()=>this.addRow=null}>${e("cancel")}</button>
          <button class="primary" @click=${()=>this.confirmAdd()}>${e(s?"make_button":"add_to_device")}</button>
        </div>
      </div>
    </div>`}renderTab(){const t=this.portList;switch(this.tab){case"devices":return I`<woow-serial-devices
          .devices=${Object.values(this.devices)}
          .states=${this.deviceStates}
          .types=${this.deviceTypes}
          .valueActions=${this.valueActions}
          .ports=${t}
          .now=${this.now}
          .t=${this.t}
          .api=${this.api}
          .portName=${this.portName}
          .open=${this.openDevice}
          @opened=${()=>this.openDevice=null}
        ></woow-serial-devices>`;case"monitor":return I`<woow-serial-monitor
          .ports=${t}
          .groups=${Object.values(this.groups)}
          .rows=${Object.values(this.rows)}
          .groupPrefix=${this.groupPrefix}
          .now=${this.now}
          .t=${this.t}
          .api=${this.api}
          .portName=${this.portName}
          @prefix-changed=${t=>this.groupPrefix={...this.groupPrefix,[t.detail.portId]:t.detail.length}}
          @add-to-device=${t=>this.startAdd(t.detail)}
          @make-button=${t=>this.startAdd(t.detail,"button")}
        ></woow-serial-monitor>`;case"sendlog":return I`<woow-serial-sendlog
          .sent=${Object.values(this.sent)}
          .ports=${t}
          .now=${this.now}
          .t=${this.t}
          .api=${this.api}
          .portName=${this.portName}
          .deviceName=${this.deviceName}
        ></woow-serial-sendlog>`;default:return I`<woow-serial-overview
          .ports=${t}
          .live=${this.live}
          .dropped=${this.dropped}
          .paused=${this.paused}
          .t=${this.t}
          .api=${this.api}
          .portName=${this.portName}
          .deviceName=${this.deviceName}
          @live-control=${this.onLiveControl}
        ></woow-serial-overview>`}}render(){const t=this.t,e={devices:Object.keys(this.devices).length,monitor:Object.keys(this.groups).length,sendlog:Object.keys(this.sent).length};return I`
      <div class="toolbar">
        ${this.narrow?I`<button @click=${this.toggleMenu} aria-label="menu">
              <svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d=${"M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"}></path></svg>
            </button>`:F}
        <div>${t("title")}</div>
      </div>
      <div class="tabs">
        ${It.map(s=>I`<button class="tab ${this.tab===s?"active":""}" @click=${()=>this.tab=s}>
            ${t(`tab_${s}`)}${e[s]?I`<span class="count">${e[s]}</span>`:F}
          </button>`)}
      </div>
      <div class="content">
        ${this.error?I`<div class="card"><div class="chip bad">${t("error",{msg:this.error})}</div></div>`:this.loaded?this.renderTab():I`<div class="empty">${t("loading")}</div>`}
      </div>
      ${this.renderAddDialog()}
    `}}Xt.styles=[Mt,n`
      :host {
        min-height: 100vh;
        background: var(--primary-background-color);
      }
      .toolbar {
        display: flex;
        align-items: center;
        gap: 8px;
        height: 56px;
        padding: 0 16px;
        background: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        font-size: 20px;
      }
      .toolbar button {
        border: none;
        background: none;
        color: inherit;
        padding: 8px;
        line-height: 0;
      }
      .tabs {
        display: flex;
        gap: 4px;
        padding: 0 12px;
        background: var(--app-header-background-color, var(--primary-color));
        overflow-x: auto;
      }
      .tab {
        border: none;
        border-bottom: 3px solid transparent;
        border-radius: 0;
        background: none;
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        opacity: 0.75;
        padding: 10px 14px;
        white-space: nowrap;
      }
      .tab.active {
        opacity: 1;
        border-bottom-color: var(--app-header-text-color, var(--text-primary-color, #fff));
      }
      .content {
        max-width: 1200px;
        margin: 0 auto;
        padding: 16px;
      }
      .count {
        margin-left: 6px;
        font-size: 0.8em;
        opacity: 0.85;
      }
      .scrim {
        position: fixed;
        inset: 0;
        z-index: 10;
        background: rgba(0, 0, 0, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
      }
      .dialog {
        width: min(460px, 100%);
        background: var(--card-background-color, #fff);
        border-radius: 12px;
        padding: 20px;
        display: grid;
        gap: 12px;
      }
      .dialog h2 {
        margin: 0;
        font-size: 1.15em;
        font-weight: 500;
      }
      .dialog label {
        display: grid;
        gap: 4px;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }
      .dialog input,
      .dialog select {
        font-size: 1.05em;
      }
    `],t([pt({attribute:!1})],Xt.prototype,"narrow",void 0),t([pt({attribute:!1})],Xt.prototype,"route",void 0),t([pt({attribute:!1})],Xt.prototype,"panel",void 0),t([ht()],Xt.prototype,"tab",void 0),t([ht()],Xt.prototype,"ports",void 0),t([ht()],Xt.prototype,"groups",void 0),t([ht()],Xt.prototype,"rows",void 0),t([ht()],Xt.prototype,"groupPrefix",void 0),t([ht()],Xt.prototype,"sent",void 0),t([ht()],Xt.prototype,"devices",void 0),t([ht()],Xt.prototype,"deviceStates",void 0),t([ht()],Xt.prototype,"deviceTypes",void 0),t([ht()],Xt.prototype,"valueActions",void 0),t([ht()],Xt.prototype,"openDevice",void 0),t([ht()],Xt.prototype,"live",void 0),t([ht()],Xt.prototype,"dropped",void 0),t([ht()],Xt.prototype,"paused",void 0),t([ht()],Xt.prototype,"loaded",void 0),t([ht()],Xt.prototype,"error",void 0),t([ht()],Xt.prototype,"now",void 0),t([ht()],Xt.prototype,"addRow",void 0),t([ht()],Xt.prototype,"addMode",void 0),t([ht()],Xt.prototype,"addTarget",void 0),t([ht()],Xt.prototype,"addName",void 0),t([ht()],Xt.prototype,"addNote",void 0),vt("woow-serial-panel",Xt);export{Xt as WoowBusPanel};
