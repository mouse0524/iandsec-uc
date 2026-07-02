import{z as ve,dc as Jt,dd as Zt,o as Ke,b3 as en,b6 as tn,c as I,r as R,cN as We,dq as tt,cM as Ve,v as d,b0 as nn,cP as at,de as Xe,cQ as on,e5 as st,O as wt,aR as yt,e6 as lt,di as Ce,G as ln,ae as xt,x as z,y as A,c8 as le,c7 as se,c6 as nt,cp as St,B as Re,A as it,cb as Ct,bD as Z,e7 as rn,dF as an,M as Fe,b1 as Ft,D as me,dm as _e,be as dt,e8 as sn,E as rt,dn as ut,dz as dn,co as un,cF as cn,cC as Be,dw as fn,bX as hn,e9 as vn,c3 as Qe,ea as ct,cd as gn,F as bn,eb as ft,ec as pn,ct as ht,dk as mn,dx as wn,cq as yn,cu as xn,cv as ot,cw as Sn,cx as Cn,cy as Fn,c0 as Rn,bU as Tn,cz as vt,cD as On,cB as Mn,cA as ae}from"./index-7ec78040.js";import{a as zn,u as Pn}from"./Input-b7771cd5.js";import{_ as kn}from"./Empty-4cd74bdc.js";function Je(e){const n=e.filter(i=>i!==void 0);if(n.length!==0)return n.length===1?n[0]:i=>{e.forEach(s=>{s&&s(i)})}}function gt(e){return e&-e}class In{constructor(n,i){this.l=n,this.min=i;const s=new Array(n+1);for(let r=0;r<n+1;++r)s[r]=0;this.ft=s}add(n,i){if(i===0)return;const{l:s,ft:r}=this;for(n+=1;n<=s;)r[n]+=i,n+=gt(n)}get(n){return this.sum(n+1)-this.sum(n)}sum(n){if(n===void 0&&(n=this.l),n<=0)return 0;const{ft:i,min:s,l:r}=this;if(n>r)throw new Error("[FinweckTree.sum]: `i` is larger than length.");let c=n*s;for(;n>0;)c+=i[n],n-=gt(n);return c}getBound(n){let i=0,s=this.l;for(;s>i;){const r=Math.floor((i+s)/2),c=this.sum(r);if(c>n){s=r;continue}else if(c<n){if(i===r)return this.sum(i+1)<=n?i+1:r;i=r}else return r}return i}}let je;function _n(){return typeof document=="undefined"?!1:(je===void 0&&("matchMedia"in window?je=window.matchMedia("(pointer:coarse)").matches:je=!1),je)}let Ze;function bt(){return typeof document=="undefined"?1:(Ze===void 0&&(Ze="chrome"in window?window.devicePixelRatio:1),Ze)}const Bn=Xe(".v-vl",{maxHeight:"inherit",height:"100%",overflow:"auto",minWidth:"1px"},[Xe("&:not(.v-vl--show-scrollbar)",{scrollbarWidth:"none"},[Xe("&::-webkit-scrollbar, &::-webkit-scrollbar-track-piece, &::-webkit-scrollbar-thumb",{width:0,height:0,display:"none"})])]),$n=ve({name:"VirtualList",inheritAttrs:!1,props:{showScrollbar:{type:Boolean,default:!0},items:{type:Array,default:()=>[]},itemSize:{type:Number,required:!0},itemResizable:Boolean,itemsStyle:[String,Object],visibleItemsTag:{type:[String,Object],default:"div"},visibleItemsProps:Object,ignoreItemResize:Boolean,onScroll:Function,onWheel:Function,onResize:Function,defaultScrollKey:[Number,String],defaultScrollIndex:Number,keyField:{type:String,default:"key"},paddingTop:{type:[Number,String],default:0},paddingBottom:{type:[Number,String],default:0}},setup(e){const n=Jt();Bn.mount({id:"vueuc/virtual-list",head:!0,anchorMetaName:Zt,ssr:n}),Ke(()=>{const{defaultScrollIndex:h,defaultScrollKey:b}=e;h!=null?w({index:h}):b!=null&&w({key:b})});let i=!1,s=!1;en(()=>{if(i=!1,!s){s=!0;return}w({top:W.value,left:x})}),tn(()=>{i=!0,s||(s=!0)});const r=I(()=>{const h=new Map,{keyField:b}=e;return e.items.forEach((p,B)=>{h.set(p[b],B)}),h}),c=R(null),g=R(void 0),a=new Map,M=I(()=>{const{items:h,itemSize:b,keyField:p}=e,B=new In(h.length,b);return h.forEach((D,L)=>{const V=D[p],j=a.get(V);j!==void 0&&B.add(L,j)}),B}),_=R(0);let x=0;const W=R(0),P=We(()=>Math.max(M.value.getBound(W.value-tt(e.paddingTop))-1,0)),T=I(()=>{const{value:h}=g;if(h===void 0)return[];const{items:b,itemSize:p}=e,B=P.value,D=Math.min(B+Math.ceil(h/p+1),b.length-1),L=[];for(let V=B;V<=D;++V)L.push(b[V]);return L}),w=(h,b)=>{if(typeof h=="number"){S(h,b,"auto");return}const{left:p,top:B,index:D,key:L,position:V,behavior:j,debounce:Q=!0}=h;if(p!==void 0||B!==void 0)S(p,B,j);else if(D!==void 0)k(D,j,Q);else if(L!==void 0){const Y=r.value.get(L);Y!==void 0&&k(Y,j,Q)}else V==="bottom"?S(0,Number.MAX_SAFE_INTEGER,j):V==="top"&&S(0,0,j)};let $,q=null;function k(h,b,p){const{value:B}=M,D=B.sum(h)+tt(e.paddingTop);if(!p)c.value.scrollTo({left:0,top:D,behavior:b});else{$=h,q!==null&&window.clearTimeout(q),q=window.setTimeout(()=>{$=void 0,q=null},16);const{scrollTop:L,offsetHeight:V}=c.value;if(D>L){const j=B.get(h);D+j<=L+V||c.value.scrollTo({left:0,top:D+j-V,behavior:b})}else c.value.scrollTo({left:0,top:D,behavior:b})}}function S(h,b,p){c.value.scrollTo({left:h,top:b,behavior:p})}function N(h,b){var p,B,D;if(i||e.ignoreItemResize||ne(b.target))return;const{value:L}=M,V=r.value.get(h),j=L.get(V),Q=(D=(B=(p=b.borderBoxSize)===null||p===void 0?void 0:p[0])===null||B===void 0?void 0:B.blockSize)!==null&&D!==void 0?D:b.contentRect.height;if(Q===j)return;Q-e.itemSize===0?a.delete(h):a.set(h,Q-e.itemSize);const X=Q-j;if(X===0)return;L.add(V,X);const o=c.value;if(o!=null){if($===void 0){const f=L.sum(V);o.scrollTop>f&&o.scrollBy(0,X)}else if(V<$)o.scrollBy(0,X);else if(V===$){const f=L.sum(V);Q+f>o.scrollTop+o.offsetHeight&&o.scrollBy(0,X)}ie()}_.value++}const H=!_n();let E=!1;function te(h){var b;(b=e.onScroll)===null||b===void 0||b.call(e,h),(!H||!E)&&ie()}function ee(h){var b;if((b=e.onWheel)===null||b===void 0||b.call(e,h),H){const p=c.value;if(p!=null){if(h.deltaX===0&&(p.scrollTop===0&&h.deltaY<=0||p.scrollTop+p.offsetHeight>=p.scrollHeight&&h.deltaY>=0))return;h.preventDefault(),p.scrollTop+=h.deltaY/bt(),p.scrollLeft+=h.deltaX/bt(),ie(),E=!0,on(()=>{E=!1})}}}function de(h){if(i||ne(h.target)||h.contentRect.height===g.value)return;g.value=h.contentRect.height;const{onResize:b}=e;b!==void 0&&b(h)}function ie(){const{value:h}=c;h!=null&&(W.value=h.scrollTop,x=h.scrollLeft)}function ne(h){let b=h;for(;b!==null;){if(b.style.display==="none")return!0;b=b.parentElement}return!1}return{listHeight:g,listStyle:{overflow:"auto"},keyToIndex:r,itemsStyle:I(()=>{const{itemResizable:h}=e,b=Ve(M.value.sum());return _.value,[e.itemsStyle,{boxSizing:"content-box",height:h?"":b,minHeight:h?b:"",paddingTop:Ve(e.paddingTop),paddingBottom:Ve(e.paddingBottom)}]}),visibleItemsStyle:I(()=>(_.value,{transform:`translateY(${Ve(M.value.sum(P.value))})`})),viewportItems:T,listElRef:c,itemsElRef:R(null),scrollTo:w,handleListResize:de,handleListScroll:te,handleListWheel:ee,handleItemResize:N}},render(){const{itemResizable:e,keyField:n,keyToIndex:i,visibleItemsTag:s}=this;return d(at,{onResize:this.handleListResize},{default:()=>{var r,c;return d("div",nn(this.$attrs,{class:["v-vl",this.showScrollbar&&"v-vl--show-scrollbar"],onScroll:this.handleListScroll,onWheel:this.handleListWheel,ref:"listElRef"}),[this.items.length!==0?d("div",{ref:"itemsElRef",class:"v-vl-items",style:this.itemsStyle},[d(s,Object.assign({class:"v-vl-visible-items",style:this.visibleItemsStyle},this.visibleItemsProps),{default:()=>this.viewportItems.map(g=>{const a=g[n],M=i.get(a),_=this.$slots.default({item:g,index:M})[0];return e?d(at,{key:a,onResize:x=>this.handleItemResize(a,x)},{default:()=>_}):(_.key=a,_)})})]):(c=(r=this.$slots).empty)===null||c===void 0?void 0:c.call(r)])}})}});function Rt(e,n){n&&(Ke(()=>{const{value:i}=e;i&&st.registerHandler(i,n)}),wt(()=>{const{value:i}=e;i&&st.unregisterHandler(i)}))}const En=ve({name:"Checkmark",render(){return d("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 16 16"},d("g",{fill:"none"},d("path",{d:"M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032z",fill:"currentColor"})))}}),An=ve({props:{onFocus:Function,onBlur:Function},setup(e){return()=>d("div",{style:"width: 0; height: 0",tabindex:0,onFocus:e.onFocus,onBlur:e.onBlur})}});function Nn(e,n){return d(xt,{name:"fade-in-scale-up-transition"},{default:()=>e?d(ln,{clsPrefix:n,class:`${n}-base-select-option__check`},{default:()=>d(En)}):null})}const pt=ve({name:"NBaseSelectOption",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(e){const{valueRef:n,pendingTmNodeRef:i,multipleRef:s,valueSetRef:r,renderLabelRef:c,renderOptionRef:g,labelFieldRef:a,valueFieldRef:M,showCheckmarkRef:_,nodePropsRef:x,handleOptionClick:W,handleOptionMouseEnter:P}=yt(lt),T=We(()=>{const{value:k}=i;return k?e.tmNode.key===k.key:!1});function w(k){const{tmNode:S}=e;S.disabled||W(k,S)}function $(k){const{tmNode:S}=e;S.disabled||P(k,S)}function q(k){const{tmNode:S}=e,{value:N}=T;S.disabled||N||P(k,S)}return{multiple:s,isGrouped:We(()=>{const{tmNode:k}=e,{parent:S}=k;return S&&S.rawNode.type==="group"}),showCheckmark:_,nodeProps:x,isPending:T,isSelected:We(()=>{const{value:k}=n,{value:S}=s;if(k===null)return!1;const N=e.tmNode.rawNode[M.value];if(S){const{value:H}=r;return H.has(N)}else return k===N}),labelField:a,renderLabel:c,renderOption:g,handleMouseMove:q,handleMouseEnter:$,handleClick:w}},render(){const{clsPrefix:e,tmNode:{rawNode:n},isSelected:i,isPending:s,isGrouped:r,showCheckmark:c,nodeProps:g,renderOption:a,renderLabel:M,handleClick:_,handleMouseEnter:x,handleMouseMove:W}=this,P=Nn(i,e),T=M?[M(n,i),c&&P]:[Ce(n[this.labelField],n,i),c&&P],w=g==null?void 0:g(n),$=d("div",Object.assign({},w,{class:[`${e}-base-select-option`,n.class,w==null?void 0:w.class,{[`${e}-base-select-option--disabled`]:n.disabled,[`${e}-base-select-option--selected`]:i,[`${e}-base-select-option--grouped`]:r,[`${e}-base-select-option--pending`]:s,[`${e}-base-select-option--show-checkmark`]:c}],style:[(w==null?void 0:w.style)||"",n.style||""],onClick:Je([_,w==null?void 0:w.onClick]),onMouseenter:Je([x,w==null?void 0:w.onMouseenter]),onMousemove:Je([W,w==null?void 0:w.onMousemove])}),d("div",{class:`${e}-base-select-option__content`},T));return n.render?n.render({node:$,option:n,selected:i}):a?a({node:$,option:n,selected:i}):$}}),mt=ve({name:"NBaseSelectGroupHeader",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){const{renderLabelRef:e,renderOptionRef:n,labelFieldRef:i,nodePropsRef:s}=yt(lt);return{labelField:i,nodeProps:s,renderLabel:e,renderOption:n}},render(){const{clsPrefix:e,renderLabel:n,renderOption:i,nodeProps:s,tmNode:{rawNode:r}}=this,c=s==null?void 0:s(r),g=n?n(r,!1):Ce(r[this.labelField],r,!1),a=d("div",Object.assign({},c,{class:[`${e}-base-select-group-header`,c==null?void 0:c.class]}),g);return r.render?r.render({node:a,option:r}):i?i({node:a,option:r,selected:!1}):a}}),Dn=z("base-select-menu",`
 line-height: 1.5;
 outline: none;
 z-index: 0;
 position: relative;
 border-radius: var(--n-border-radius);
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-color);
`,[z("scrollbar",`
 max-height: var(--n-height);
 `),z("virtual-list",`
 max-height: var(--n-height);
 `),z("base-select-option",`
 min-height: var(--n-option-height);
 font-size: var(--n-option-font-size);
 display: flex;
 align-items: center;
 `,[A("content",`
 z-index: 1;
 white-space: nowrap;
 text-overflow: ellipsis;
 overflow: hidden;
 `)]),z("base-select-group-header",`
 min-height: var(--n-option-height);
 font-size: .93em;
 display: flex;
 align-items: center;
 `),z("base-select-menu-option-wrapper",`
 position: relative;
 width: 100%;
 `),A("loading, empty",`
 display: flex;
 padding: 12px 32px;
 flex: 1;
 justify-content: center;
 `),A("loading",`
 color: var(--n-loading-color);
 font-size: var(--n-loading-size);
 `),A("header",`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),A("action",`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-top: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),z("base-select-group-header",`
 position: relative;
 cursor: default;
 padding: var(--n-option-padding);
 color: var(--n-group-header-text-color);
 `),z("base-select-option",`
 cursor: pointer;
 position: relative;
 padding: var(--n-option-padding);
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 box-sizing: border-box;
 color: var(--n-option-text-color);
 opacity: 1;
 `,[le("show-checkmark",`
 padding-right: calc(var(--n-option-padding-right) + 20px);
 `),se("&::before",`
 content: "";
 position: absolute;
 left: 4px;
 right: 4px;
 top: 0;
 bottom: 0;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),se("&:active",`
 color: var(--n-option-text-color-pressed);
 `),le("grouped",`
 padding-left: calc(var(--n-option-padding-left) * 1.5);
 `),le("pending",[se("&::before",`
 background-color: var(--n-option-color-pending);
 `)]),le("selected",`
 color: var(--n-option-text-color-active);
 `,[se("&::before",`
 background-color: var(--n-option-color-active);
 `),le("pending",[se("&::before",`
 background-color: var(--n-option-color-active-pending);
 `)])]),le("disabled",`
 cursor: not-allowed;
 `,[nt("selected",`
 color: var(--n-option-text-color-disabled);
 `),le("selected",`
 opacity: var(--n-option-opacity-disabled);
 `)]),A("check",`
 font-size: 16px;
 position: absolute;
 right: calc(var(--n-option-padding-right) - 4px);
 top: calc(50% - 7px);
 color: var(--n-option-check-color);
 transition: color .3s var(--n-bezier);
 `,[St({enterScale:"0.5"})])])]),Ln=ve({name:"InternalSelectMenu",props:Object.assign(Object.assign({},Re.props),{clsPrefix:{type:String,required:!0},scrollable:{type:Boolean,default:!0},treeMate:{type:Object,required:!0},multiple:Boolean,size:{type:String,default:"medium"},value:{type:[String,Number,Array],default:null},autoPending:Boolean,virtualScroll:{type:Boolean,default:!0},show:{type:Boolean,default:!0},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},loading:Boolean,focusable:Boolean,renderLabel:Function,renderOption:Function,nodeProps:Function,showCheckmark:{type:Boolean,default:!0},onMousedown:Function,onScroll:Function,onFocus:Function,onBlur:Function,onKeyup:Function,onKeydown:Function,onTabOut:Function,onMouseenter:Function,onMouseleave:Function,onResize:Function,resetMenuOnOptionsChange:{type:Boolean,default:!0},inlineThemeDisabled:Boolean,onToggle:Function}),setup(e){const{mergedClsPrefixRef:n,mergedRtlRef:i}=it(e),s=Ct("InternalSelectMenu",i,n),r=Re("InternalSelectMenu","-internal-select-menu",Dn,rn,e,Z(e,"clsPrefix")),c=R(null),g=R(null),a=R(null),M=I(()=>e.treeMate.getFlattenedNodes()),_=I(()=>an(M.value)),x=R(null);function W(){const{treeMate:o}=e;let f=null;const{value:K}=e;K===null?f=o.getFirstAvailableNode():(e.multiple?f=o.getNode((K||[])[(K||[]).length-1]):f=o.getNode(K),(!f||f.disabled)&&(f=o.getFirstAvailableNode())),B(f||null)}function P(){const{value:o}=x;o&&!e.treeMate.getNode(o.key)&&(x.value=null)}let T;Fe(()=>e.show,o=>{o?T=Fe(()=>e.treeMate,()=>{e.resetMenuOnOptionsChange?(e.autoPending?W():P(),Ft(D)):P()},{immediate:!0}):T==null||T()},{immediate:!0}),wt(()=>{T==null||T()});const w=I(()=>tt(r.value.self[me("optionHeight",e.size)])),$=I(()=>_e(r.value.self[me("padding",e.size)])),q=I(()=>e.multiple&&Array.isArray(e.value)?new Set(e.value):new Set),k=I(()=>{const o=M.value;return o&&o.length===0});function S(o){const{onToggle:f}=e;f&&f(o)}function N(o){const{onScroll:f}=e;f&&f(o)}function H(o){var f;(f=a.value)===null||f===void 0||f.sync(),N(o)}function E(){var o;(o=a.value)===null||o===void 0||o.sync()}function te(){const{value:o}=x;return o||null}function ee(o,f){f.disabled||B(f,!1)}function de(o,f){f.disabled||S(f)}function ie(o){var f;Be(o,"action")||(f=e.onKeyup)===null||f===void 0||f.call(e,o)}function ne(o){var f;Be(o,"action")||(f=e.onKeydown)===null||f===void 0||f.call(e,o)}function h(o){var f;(f=e.onMousedown)===null||f===void 0||f.call(e,o),!e.focusable&&o.preventDefault()}function b(){const{value:o}=x;o&&B(o.getNext({loop:!0}),!0)}function p(){const{value:o}=x;o&&B(o.getPrev({loop:!0}),!0)}function B(o,f=!1){x.value=o,f&&D()}function D(){var o,f;const K=x.value;if(!K)return;const ue=_.value(K.key);ue!==null&&(e.virtualScroll?(o=g.value)===null||o===void 0||o.scrollTo({index:ue}):(f=a.value)===null||f===void 0||f.scrollTo({index:ue,elSize:w.value}))}function L(o){var f,K;!((f=c.value)===null||f===void 0)&&f.contains(o.target)&&((K=e.onFocus)===null||K===void 0||K.call(e,o))}function V(o){var f,K;!((f=c.value)===null||f===void 0)&&f.contains(o.relatedTarget)||(K=e.onBlur)===null||K===void 0||K.call(e,o)}dt(lt,{handleOptionMouseEnter:ee,handleOptionClick:de,valueSetRef:q,pendingTmNodeRef:x,nodePropsRef:Z(e,"nodeProps"),showCheckmarkRef:Z(e,"showCheckmark"),multipleRef:Z(e,"multiple"),valueRef:Z(e,"value"),renderLabelRef:Z(e,"renderLabel"),renderOptionRef:Z(e,"renderOption"),labelFieldRef:Z(e,"labelField"),valueFieldRef:Z(e,"valueField")}),dt(sn,c),Ke(()=>{const{value:o}=a;o&&o.sync()});const j=I(()=>{const{size:o}=e,{common:{cubicBezierEaseInOut:f},self:{height:K,borderRadius:ue,color:we,groupHeaderTextColor:ye,actionDividerColor:ce,optionTextColorPressed:oe,optionTextColor:xe,optionTextColorDisabled:fe,optionTextColorActive:Te,optionOpacityDisabled:Oe,optionCheckColor:Me,actionTextColor:ze,optionColorPending:ge,optionColorActive:be,loadingColor:Pe,loadingSize:ke,optionColorActivePending:Ie,[me("optionFontSize",o)]:Se,[me("optionHeight",o)]:pe,[me("optionPadding",o)]:J}}=r.value;return{"--n-height":K,"--n-action-divider-color":ce,"--n-action-text-color":ze,"--n-bezier":f,"--n-border-radius":ue,"--n-color":we,"--n-option-font-size":Se,"--n-group-header-text-color":ye,"--n-option-check-color":Me,"--n-option-color-pending":ge,"--n-option-color-active":be,"--n-option-color-active-pending":Ie,"--n-option-height":pe,"--n-option-opacity-disabled":Oe,"--n-option-text-color":xe,"--n-option-text-color-active":Te,"--n-option-text-color-disabled":fe,"--n-option-text-color-pressed":oe,"--n-option-padding":J,"--n-option-padding-left":_e(J,"left"),"--n-option-padding-right":_e(J,"right"),"--n-loading-color":Pe,"--n-loading-size":ke}}),{inlineThemeDisabled:Q}=e,Y=Q?rt("internal-select-menu",I(()=>e.size[0]),j,e):void 0,X={selfRef:c,next:b,prev:p,getPendingTmNode:te};return Rt(c,e.onResize),Object.assign({mergedTheme:r,mergedClsPrefix:n,rtlEnabled:s,virtualListRef:g,scrollbarRef:a,itemSize:w,padding:$,flattenedNodes:M,empty:k,virtualListContainer(){const{value:o}=g;return o==null?void 0:o.listElRef},virtualListContent(){const{value:o}=g;return o==null?void 0:o.itemsElRef},doScroll:N,handleFocusin:L,handleFocusout:V,handleKeyUp:ie,handleKeyDown:ne,handleMouseDown:h,handleVirtualListResize:E,handleVirtualListScroll:H,cssVars:Q?void 0:j,themeClass:Y==null?void 0:Y.themeClass,onRender:Y==null?void 0:Y.onRender},X)},render(){const{$slots:e,virtualScroll:n,clsPrefix:i,mergedTheme:s,themeClass:r,onRender:c}=this;return c==null||c(),d("div",{ref:"selfRef",tabindex:this.focusable?0:-1,class:[`${i}-base-select-menu`,this.rtlEnabled&&`${i}-base-select-menu--rtl`,r,this.multiple&&`${i}-base-select-menu--multiple`],style:this.cssVars,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onKeyup:this.handleKeyUp,onKeydown:this.handleKeyDown,onMousedown:this.handleMouseDown,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},ut(e.header,g=>g&&d("div",{class:`${i}-base-select-menu__header`,"data-header":!0,key:"header"},g)),this.loading?d("div",{class:`${i}-base-select-menu__loading`},d(dn,{clsPrefix:i,strokeWidth:20})):this.empty?d("div",{class:`${i}-base-select-menu__empty`,"data-empty":!0},cn(e.empty,()=>[d(kn,{theme:s.peers.Empty,themeOverrides:s.peerOverrides.Empty})])):d(un,{ref:"scrollbarRef",theme:s.peers.Scrollbar,themeOverrides:s.peerOverrides.Scrollbar,scrollable:this.scrollable,container:n?this.virtualListContainer:void 0,content:n?this.virtualListContent:void 0,onScroll:n?void 0:this.doScroll},{default:()=>n?d($n,{ref:"virtualListRef",class:`${i}-virtual-list`,items:this.flattenedNodes,itemSize:this.itemSize,showScrollbar:!1,paddingTop:this.padding.top,paddingBottom:this.padding.bottom,onResize:this.handleVirtualListResize,onScroll:this.handleVirtualListScroll,itemResizable:!0},{default:({item:g})=>g.isGroup?d(mt,{key:g.key,clsPrefix:i,tmNode:g}):g.ignored?null:d(pt,{clsPrefix:i,key:g.key,tmNode:g})}):d("div",{class:`${i}-base-select-menu-option-wrapper`,style:{paddingTop:this.padding.top,paddingBottom:this.padding.bottom}},this.flattenedNodes.map(g=>g.isGroup?d(mt,{key:g.key,clsPrefix:i,tmNode:g}):d(pt,{clsPrefix:i,key:g.key,tmNode:g})))}),ut(e.action,g=>g&&[d("div",{class:`${i}-base-select-menu__action`,"data-action":!0,key:"action"},g),d(An,{onFocus:this.onTabOut,key:"focus-detector"})]))}}),Vn=se([z("base-selection",`
 --n-padding-single: var(--n-padding-single-top) var(--n-padding-single-right) var(--n-padding-single-bottom) var(--n-padding-single-left);
 --n-padding-multiple: var(--n-padding-multiple-top) var(--n-padding-multiple-right) var(--n-padding-multiple-bottom) var(--n-padding-multiple-left);
 position: relative;
 z-index: auto;
 box-shadow: none;
 width: 100%;
 max-width: 100%;
 display: inline-block;
 vertical-align: bottom;
 border-radius: var(--n-border-radius);
 min-height: var(--n-height);
 line-height: 1.5;
 font-size: var(--n-font-size);
 `,[z("base-loading",`
 color: var(--n-loading-color);
 `),z("base-selection-tags","min-height: var(--n-height);"),A("border, state-border",`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 pointer-events: none;
 border: var(--n-border);
 border-radius: inherit;
 transition:
 box-shadow .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `),A("state-border",`
 z-index: 1;
 border-color: #0000;
 `),z("base-suffix",`
 cursor: pointer;
 position: absolute;
 top: 50%;
 transform: translateY(-50%);
 right: 10px;
 `,[A("arrow",`
 font-size: var(--n-arrow-size);
 color: var(--n-arrow-color);
 transition: color .3s var(--n-bezier);
 `)]),z("base-selection-overlay",`
 display: flex;
 align-items: center;
 white-space: nowrap;
 pointer-events: none;
 position: absolute;
 top: 0;
 right: 0;
 bottom: 0;
 left: 0;
 padding: var(--n-padding-single);
 transition: color .3s var(--n-bezier);
 `,[A("wrapper",`
 flex-basis: 0;
 flex-grow: 1;
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),z("base-selection-placeholder",`
 color: var(--n-placeholder-color);
 `,[A("inner",`
 max-width: 100%;
 overflow: hidden;
 `)]),z("base-selection-tags",`
 cursor: pointer;
 outline: none;
 box-sizing: border-box;
 position: relative;
 z-index: auto;
 display: flex;
 padding: var(--n-padding-multiple);
 flex-wrap: wrap;
 align-items: center;
 width: 100%;
 vertical-align: bottom;
 background-color: var(--n-color);
 border-radius: inherit;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `),z("base-selection-label",`
 height: var(--n-height);
 display: inline-flex;
 width: 100%;
 vertical-align: bottom;
 cursor: pointer;
 outline: none;
 z-index: auto;
 box-sizing: border-box;
 position: relative;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 border-radius: inherit;
 background-color: var(--n-color);
 align-items: center;
 `,[z("base-selection-input",`
 font-size: inherit;
 line-height: inherit;
 outline: none;
 cursor: pointer;
 box-sizing: border-box;
 border:none;
 width: 100%;
 padding: var(--n-padding-single);
 background-color: #0000;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 caret-color: var(--n-caret-color);
 `,[A("content",`
 text-overflow: ellipsis;
 overflow: hidden;
 white-space: nowrap; 
 `)]),A("render-label",`
 color: var(--n-text-color);
 `)]),nt("disabled",[se("&:hover",[A("state-border",`
 box-shadow: var(--n-box-shadow-hover);
 border: var(--n-border-hover);
 `)]),le("focus",[A("state-border",`
 box-shadow: var(--n-box-shadow-focus);
 border: var(--n-border-focus);
 `)]),le("active",[A("state-border",`
 box-shadow: var(--n-box-shadow-active);
 border: var(--n-border-active);
 `),z("base-selection-label","background-color: var(--n-color-active);"),z("base-selection-tags","background-color: var(--n-color-active);")])]),le("disabled","cursor: not-allowed;",[A("arrow",`
 color: var(--n-arrow-color-disabled);
 `),z("base-selection-label",`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `,[z("base-selection-input",`
 cursor: not-allowed;
 color: var(--n-text-color-disabled);
 `),A("render-label",`
 color: var(--n-text-color-disabled);
 `)]),z("base-selection-tags",`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `),z("base-selection-placeholder",`
 cursor: not-allowed;
 color: var(--n-placeholder-color-disabled);
 `)]),z("base-selection-input-tag",`
 height: calc(var(--n-height) - 6px);
 line-height: calc(var(--n-height) - 6px);
 outline: none;
 display: none;
 position: relative;
 margin-bottom: 3px;
 max-width: 100%;
 vertical-align: bottom;
 `,[A("input",`
 font-size: inherit;
 font-family: inherit;
 min-width: 1px;
 padding: 0;
 background-color: #0000;
 outline: none;
 border: none;
 max-width: 100%;
 overflow: hidden;
 width: 1em;
 line-height: inherit;
 cursor: pointer;
 color: var(--n-text-color);
 caret-color: var(--n-caret-color);
 `),A("mirror",`
 position: absolute;
 left: 0;
 top: 0;
 white-space: pre;
 visibility: hidden;
 user-select: none;
 -webkit-user-select: none;
 opacity: 0;
 `)]),["warning","error"].map(e=>le(`${e}-status`,[A("state-border",`border: var(--n-border-${e});`),nt("disabled",[se("&:hover",[A("state-border",`
 box-shadow: var(--n-box-shadow-hover-${e});
 border: var(--n-border-hover-${e});
 `)]),le("active",[A("state-border",`
 box-shadow: var(--n-box-shadow-active-${e});
 border: var(--n-border-active-${e});
 `),z("base-selection-label",`background-color: var(--n-color-active-${e});`),z("base-selection-tags",`background-color: var(--n-color-active-${e});`)]),le("focus",[A("state-border",`
 box-shadow: var(--n-box-shadow-focus-${e});
 border: var(--n-border-focus-${e});
 `)])])]))]),z("base-selection-popover",`
 margin-bottom: -3px;
 display: flex;
 flex-wrap: wrap;
 margin-right: -8px;
 `),z("base-selection-tag-wrapper",`
 max-width: 100%;
 display: inline-flex;
 padding: 0 7px 3px 0;
 `,[se("&:last-child","padding-right: 0;"),z("tag",`
 font-size: 14px;
 max-width: 100%;
 `,[A("content",`
 line-height: 1.25;
 text-overflow: ellipsis;
 overflow: hidden;
 `)])])]),jn=ve({name:"InternalSelection",props:Object.assign(Object.assign({},Re.props),{clsPrefix:{type:String,required:!0},bordered:{type:Boolean,default:void 0},active:Boolean,pattern:{type:String,default:""},placeholder:String,selectedOption:{type:Object,default:null},selectedOptions:{type:Array,default:null},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},multiple:Boolean,filterable:Boolean,clearable:Boolean,disabled:Boolean,size:{type:String,default:"medium"},loading:Boolean,autofocus:Boolean,showArrow:{type:Boolean,default:!0},inputProps:Object,focused:Boolean,renderTag:Function,onKeydown:Function,onClick:Function,onBlur:Function,onFocus:Function,onDeleteOption:Function,maxTagCount:[String,Number],ellipsisTagPopoverProps:Object,onClear:Function,onPatternInput:Function,onPatternFocus:Function,onPatternBlur:Function,renderLabel:Function,status:String,inlineThemeDisabled:Boolean,ignoreComposition:{type:Boolean,default:!0},onResize:Function}),setup(e){const{mergedClsPrefixRef:n,mergedRtlRef:i}=it(e),s=Ct("InternalSelection",i,n),r=R(null),c=R(null),g=R(null),a=R(null),M=R(null),_=R(null),x=R(null),W=R(null),P=R(null),T=R(null),w=R(!1),$=R(!1),q=R(!1),k=Re("InternalSelection","-internal-selection",Vn,fn,e,Z(e,"clsPrefix")),S=I(()=>e.clearable&&!e.disabled&&(q.value||e.active)),N=I(()=>e.selectedOption?e.renderTag?e.renderTag({option:e.selectedOption,handleClose:()=>{}}):e.renderLabel?e.renderLabel(e.selectedOption,!0):Ce(e.selectedOption[e.labelField],e.selectedOption,!0):e.placeholder),H=I(()=>{const l=e.selectedOption;if(l)return l[e.labelField]}),E=I(()=>e.multiple?!!(Array.isArray(e.selectedOptions)&&e.selectedOptions.length):e.selectedOption!==null);function te(){var l;const{value:v}=r;if(v){const{value:U}=c;U&&(U.style.width=`${v.offsetWidth}px`,e.maxTagCount!=="responsive"&&((l=P.value)===null||l===void 0||l.sync({showAllItemsBeforeCalculate:!1})))}}function ee(){const{value:l}=T;l&&(l.style.display="none")}function de(){const{value:l}=T;l&&(l.style.display="inline-block")}Fe(Z(e,"active"),l=>{l||ee()}),Fe(Z(e,"pattern"),()=>{e.multiple&&Ft(te)});function ie(l){const{onFocus:v}=e;v&&v(l)}function ne(l){const{onBlur:v}=e;v&&v(l)}function h(l){const{onDeleteOption:v}=e;v&&v(l)}function b(l){const{onClear:v}=e;v&&v(l)}function p(l){const{onPatternInput:v}=e;v&&v(l)}function B(l){var v;(!l.relatedTarget||!(!((v=g.value)===null||v===void 0)&&v.contains(l.relatedTarget)))&&ie(l)}function D(l){var v;!((v=g.value)===null||v===void 0)&&v.contains(l.relatedTarget)||ne(l)}function L(l){b(l)}function V(){q.value=!0}function j(){q.value=!1}function Q(l){!e.active||!e.filterable||l.target!==c.value&&l.preventDefault()}function Y(l){h(l)}const X=R(!1);function o(l){if(l.key==="Backspace"&&!X.value&&!e.pattern.length){const{selectedOptions:v}=e;v!=null&&v.length&&Y(v[v.length-1])}}let f=null;function K(l){const{value:v}=r;if(v){const U=l.target.value;v.textContent=U,te()}e.ignoreComposition&&X.value?f=l:p(l)}function ue(){X.value=!0}function we(){X.value=!1,e.ignoreComposition&&p(f),f=null}function ye(l){var v;$.value=!0,(v=e.onPatternFocus)===null||v===void 0||v.call(e,l)}function ce(l){var v;$.value=!1,(v=e.onPatternBlur)===null||v===void 0||v.call(e,l)}function oe(){var l,v;if(e.filterable)$.value=!1,(l=_.value)===null||l===void 0||l.blur(),(v=c.value)===null||v===void 0||v.blur();else if(e.multiple){const{value:U}=a;U==null||U.blur()}else{const{value:U}=M;U==null||U.blur()}}function xe(){var l,v,U;e.filterable?($.value=!1,(l=_.value)===null||l===void 0||l.focus()):e.multiple?(v=a.value)===null||v===void 0||v.focus():(U=M.value)===null||U===void 0||U.focus()}function fe(){const{value:l}=c;l&&(de(),l.focus())}function Te(){const{value:l}=c;l&&l.blur()}function Oe(l){const{value:v}=x;v&&v.setTextContent(`+${l}`)}function Me(){const{value:l}=W;return l}function ze(){return c.value}let ge=null;function be(){ge!==null&&window.clearTimeout(ge)}function Pe(){e.active||(be(),ge=window.setTimeout(()=>{E.value&&(w.value=!0)},100))}function ke(){be()}function Ie(l){l||(be(),w.value=!1)}Fe(E,l=>{l||(w.value=!1)}),Ke(()=>{hn(()=>{const l=_.value;l&&(e.disabled?l.removeAttribute("tabindex"):l.tabIndex=$.value?-1:0)})}),Rt(g,e.onResize);const{inlineThemeDisabled:Se}=e,pe=I(()=>{const{size:l}=e,{common:{cubicBezierEaseInOut:v},self:{borderRadius:U,color:Ue,placeholderColor:qe,textColor:$e,paddingSingle:Ee,paddingMultiple:Ae,caretColor:Ge,colorDisabled:Ye,textColorDisabled:Ne,placeholderColorDisabled:he,colorActive:t,boxShadowFocus:u,boxShadowActive:m,boxShadowHover:O,border:C,borderFocus:y,borderHover:F,borderActive:G,arrowColor:re,arrowColorDisabled:Ot,loadingColor:Mt,colorActiveWarning:zt,boxShadowFocusWarning:Pt,boxShadowActiveWarning:kt,boxShadowHoverWarning:It,borderWarning:_t,borderFocusWarning:Bt,borderHoverWarning:$t,borderActiveWarning:Et,colorActiveError:At,boxShadowFocusError:Nt,boxShadowActiveError:Dt,boxShadowHoverError:Lt,borderError:Vt,borderFocusError:jt,borderHoverError:Wt,borderActiveError:Ht,clearColor:Kt,clearColorHover:Ut,clearColorPressed:qt,clearSize:Gt,arrowSize:Yt,[me("height",l)]:Xt,[me("fontSize",l)]:Qt}}=k.value,De=_e(Ee),Le=_e(Ae);return{"--n-bezier":v,"--n-border":C,"--n-border-active":G,"--n-border-focus":y,"--n-border-hover":F,"--n-border-radius":U,"--n-box-shadow-active":m,"--n-box-shadow-focus":u,"--n-box-shadow-hover":O,"--n-caret-color":Ge,"--n-color":Ue,"--n-color-active":t,"--n-color-disabled":Ye,"--n-font-size":Qt,"--n-height":Xt,"--n-padding-single-top":De.top,"--n-padding-multiple-top":Le.top,"--n-padding-single-right":De.right,"--n-padding-multiple-right":Le.right,"--n-padding-single-left":De.left,"--n-padding-multiple-left":Le.left,"--n-padding-single-bottom":De.bottom,"--n-padding-multiple-bottom":Le.bottom,"--n-placeholder-color":qe,"--n-placeholder-color-disabled":he,"--n-text-color":$e,"--n-text-color-disabled":Ne,"--n-arrow-color":re,"--n-arrow-color-disabled":Ot,"--n-loading-color":Mt,"--n-color-active-warning":zt,"--n-box-shadow-focus-warning":Pt,"--n-box-shadow-active-warning":kt,"--n-box-shadow-hover-warning":It,"--n-border-warning":_t,"--n-border-focus-warning":Bt,"--n-border-hover-warning":$t,"--n-border-active-warning":Et,"--n-color-active-error":At,"--n-box-shadow-focus-error":Nt,"--n-box-shadow-active-error":Dt,"--n-box-shadow-hover-error":Lt,"--n-border-error":Vt,"--n-border-focus-error":jt,"--n-border-hover-error":Wt,"--n-border-active-error":Ht,"--n-clear-size":Gt,"--n-clear-color":Kt,"--n-clear-color-hover":Ut,"--n-clear-color-pressed":qt,"--n-arrow-size":Yt}}),J=Se?rt("internal-selection",I(()=>e.size[0]),pe,e):void 0;return{mergedTheme:k,mergedClearable:S,mergedClsPrefix:n,rtlEnabled:s,patternInputFocused:$,filterablePlaceholder:N,label:H,selected:E,showTagsPanel:w,isComposing:X,counterRef:x,counterWrapperRef:W,patternInputMirrorRef:r,patternInputRef:c,selfRef:g,multipleElRef:a,singleElRef:M,patternInputWrapperRef:_,overflowRef:P,inputTagElRef:T,handleMouseDown:Q,handleFocusin:B,handleClear:L,handleMouseEnter:V,handleMouseLeave:j,handleDeleteOption:Y,handlePatternKeyDown:o,handlePatternInputInput:K,handlePatternInputBlur:ce,handlePatternInputFocus:ye,handleMouseEnterCounter:Pe,handleMouseLeaveCounter:ke,handleFocusout:D,handleCompositionEnd:we,handleCompositionStart:ue,onPopoverUpdateShow:Ie,focus:xe,focusInput:fe,blur:oe,blurInput:Te,updateCounter:Oe,getCounter:Me,getTail:ze,renderLabel:e.renderLabel,cssVars:Se?void 0:pe,themeClass:J==null?void 0:J.themeClass,onRender:J==null?void 0:J.onRender}},render(){const{status:e,multiple:n,size:i,disabled:s,filterable:r,maxTagCount:c,bordered:g,clsPrefix:a,ellipsisTagPopoverProps:M,onRender:_,renderTag:x,renderLabel:W}=this;_==null||_();const P=c==="responsive",T=typeof c=="number",w=P||T,$=d(vn,null,{default:()=>d(zn,{clsPrefix:a,loading:this.loading,showArrow:this.showArrow,showClear:this.mergedClearable&&this.selected,onClear:this.handleClear},{default:()=>{var k,S;return(S=(k=this.$slots).arrow)===null||S===void 0?void 0:S.call(k)}})});let q;if(n){const{labelField:k}=this,S=p=>d("div",{class:`${a}-base-selection-tag-wrapper`,key:p.value},x?x({option:p,handleClose:()=>{this.handleDeleteOption(p)}}):d(Qe,{size:i,closable:!p.disabled,disabled:s,onClose:()=>{this.handleDeleteOption(p)},internalCloseIsButtonTag:!1,internalCloseFocusable:!1},{default:()=>W?W(p,!0):Ce(p[k],p,!0)})),N=()=>(T?this.selectedOptions.slice(0,c):this.selectedOptions).map(S),H=r?d("div",{class:`${a}-base-selection-input-tag`,ref:"inputTagElRef",key:"__input-tag__"},d("input",Object.assign({},this.inputProps,{ref:"patternInputRef",tabindex:-1,disabled:s,value:this.pattern,autofocus:this.autofocus,class:`${a}-base-selection-input-tag__input`,onBlur:this.handlePatternInputBlur,onFocus:this.handlePatternInputFocus,onKeydown:this.handlePatternKeyDown,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),d("span",{ref:"patternInputMirrorRef",class:`${a}-base-selection-input-tag__mirror`},this.pattern)):null,E=P?()=>d("div",{class:`${a}-base-selection-tag-wrapper`,ref:"counterWrapperRef"},d(Qe,{size:i,ref:"counterRef",onMouseenter:this.handleMouseEnterCounter,onMouseleave:this.handleMouseLeaveCounter,disabled:s})):void 0;let te;if(T){const p=this.selectedOptions.length-c;p>0&&(te=d("div",{class:`${a}-base-selection-tag-wrapper`,key:"__counter__"},d(Qe,{size:i,ref:"counterRef",onMouseenter:this.handleMouseEnterCounter,disabled:s},{default:()=>`+${p}`})))}const ee=P?r?d(ct,{ref:"overflowRef",updateCounter:this.updateCounter,getCounter:this.getCounter,getTail:this.getTail,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:N,counter:E,tail:()=>H}):d(ct,{ref:"overflowRef",updateCounter:this.updateCounter,getCounter:this.getCounter,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:N,counter:E}):T&&te?N().concat(te):N(),de=w?()=>d("div",{class:`${a}-base-selection-popover`},P?N():this.selectedOptions.map(S)):void 0,ie=w?Object.assign({show:this.showTagsPanel,trigger:"hover",overlap:!0,placement:"top",width:"trigger",onUpdateShow:this.onPopoverUpdateShow,theme:this.mergedTheme.peers.Popover,themeOverrides:this.mergedTheme.peerOverrides.Popover},M):null,h=(this.selected?!1:this.active?!this.pattern&&!this.isComposing:!0)?d("div",{class:`${a}-base-selection-placeholder ${a}-base-selection-overlay`},d("div",{class:`${a}-base-selection-placeholder__inner`},this.placeholder)):null,b=r?d("div",{ref:"patternInputWrapperRef",class:`${a}-base-selection-tags`},ee,P?null:H,$):d("div",{ref:"multipleElRef",class:`${a}-base-selection-tags`,tabindex:s?void 0:0},ee,$);q=d(bn,null,w?d(gn,Object.assign({},ie,{scrollable:!0,style:"max-height: calc(var(--v-target-height) * 6.6);"}),{trigger:()=>b,default:de}):b,h)}else if(r){const k=this.pattern||this.isComposing,S=this.active?!k:!this.selected,N=this.active?!1:this.selected;q=d("div",{ref:"patternInputWrapperRef",class:`${a}-base-selection-label`,title:this.patternInputFocused?void 0:ft(this.label)},d("input",Object.assign({},this.inputProps,{ref:"patternInputRef",class:`${a}-base-selection-input`,value:this.active?this.pattern:"",placeholder:"",readonly:s,disabled:s,tabindex:-1,autofocus:this.autofocus,onFocus:this.handlePatternInputFocus,onBlur:this.handlePatternInputBlur,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),N?d("div",{class:`${a}-base-selection-label__render-label ${a}-base-selection-overlay`,key:"input"},d("div",{class:`${a}-base-selection-overlay__wrapper`},x?x({option:this.selectedOption,handleClose:()=>{}}):W?W(this.selectedOption,!0):Ce(this.label,this.selectedOption,!0))):null,S?d("div",{class:`${a}-base-selection-placeholder ${a}-base-selection-overlay`,key:"placeholder"},d("div",{class:`${a}-base-selection-overlay__wrapper`},this.filterablePlaceholder)):null,$)}else q=d("div",{ref:"singleElRef",class:`${a}-base-selection-label`,tabindex:this.disabled?void 0:0},this.label!==void 0?d("div",{class:`${a}-base-selection-input`,title:ft(this.label),key:"input"},d("div",{class:`${a}-base-selection-input__content`},x?x({option:this.selectedOption,handleClose:()=>{}}):W?W(this.selectedOption,!0):Ce(this.label,this.selectedOption,!0))):d("div",{class:`${a}-base-selection-placeholder ${a}-base-selection-overlay`,key:"placeholder"},d("div",{class:`${a}-base-selection-placeholder__inner`},this.placeholder)),$);return d("div",{ref:"selfRef",class:[`${a}-base-selection`,this.rtlEnabled&&`${a}-base-selection--rtl`,this.themeClass,e&&`${a}-base-selection--${e}-status`,{[`${a}-base-selection--active`]:this.active,[`${a}-base-selection--selected`]:this.selected||this.active&&this.pattern,[`${a}-base-selection--disabled`]:this.disabled,[`${a}-base-selection--multiple`]:this.multiple,[`${a}-base-selection--focus`]:this.focused}],style:this.cssVars,onClick:this.onClick,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onKeydown:this.onKeydown,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onMousedown:this.handleMouseDown},q,g?d("div",{class:`${a}-base-selection__border`}):null,g?d("div",{class:`${a}-base-selection__state-border`}):null)}});function He(e){return e.type==="group"}function Tt(e){return e.type==="ignored"}function et(e,n){try{return!!(1+n.toString().toLowerCase().indexOf(e.trim().toLowerCase()))}catch(i){return!1}}function Wn(e,n){return{getIsGroup:He,getIgnored:Tt,getKey(s){return He(s)?s.name||s.key||"key-required":s[e]},getChildren(s){return s[n]}}}function Hn(e,n,i,s){if(!n)return e;function r(c){if(!Array.isArray(c))return[];const g=[];for(const a of c)if(He(a)){const M=r(a[s]);M.length&&g.push(Object.assign({},a,{[s]:M}))}else{if(Tt(a))continue;n(i,a)&&g.push(a)}return g}return r(e)}function Kn(e,n,i){const s=new Map;return e.forEach(r=>{He(r)?r[i].forEach(c=>{s.set(c[n],c)}):s.set(r[n],r)}),s}const Un=se([z("select",`
 z-index: auto;
 outline: none;
 width: 100%;
 position: relative;
 `),z("select-menu",`
 margin: 4px 0;
 box-shadow: var(--n-menu-box-shadow);
 `,[St({originalTransition:"background-color .3s var(--n-bezier), box-shadow .3s var(--n-bezier)"})])]),qn=Object.assign(Object.assign({},Re.props),{to:ot.propTo,bordered:{type:Boolean,default:void 0},clearable:Boolean,clearFilterAfterSelect:{type:Boolean,default:!0},options:{type:Array,default:()=>[]},defaultValue:{type:[String,Number,Array],default:null},keyboard:{type:Boolean,default:!0},value:[String,Number,Array],placeholder:String,menuProps:Object,multiple:Boolean,size:String,filterable:Boolean,disabled:{type:Boolean,default:void 0},remote:Boolean,loading:Boolean,filter:Function,placement:{type:String,default:"bottom-start"},widthMode:{type:String,default:"trigger"},tag:Boolean,onCreate:Function,fallbackOption:{type:[Function,Boolean],default:void 0},show:{type:Boolean,default:void 0},showArrow:{type:Boolean,default:!0},maxTagCount:[Number,String],ellipsisTagPopoverProps:Object,consistentMenuWidth:{type:Boolean,default:!0},virtualScroll:{type:Boolean,default:!0},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},childrenField:{type:String,default:"children"},renderLabel:Function,renderOption:Function,renderTag:Function,"onUpdate:value":[Function,Array],inputProps:Object,nodeProps:Function,ignoreComposition:{type:Boolean,default:!0},showOnFocus:Boolean,onUpdateValue:[Function,Array],onBlur:[Function,Array],onClear:[Function,Array],onFocus:[Function,Array],onScroll:[Function,Array],onSearch:[Function,Array],onUpdateShow:[Function,Array],"onUpdate:show":[Function,Array],displayDirective:{type:String,default:"show"},resetMenuOnOptionsChange:{type:Boolean,default:!0},status:String,showCheckmark:{type:Boolean,default:!0},onChange:[Function,Array],items:Array}),Qn=ve({name:"Select",props:qn,setup(e){const{mergedClsPrefixRef:n,mergedBorderedRef:i,namespaceRef:s,inlineThemeDisabled:r}=it(e),c=Re("Select","-select",Un,pn,e,n),g=R(e.defaultValue),a=Z(e,"value"),M=ht(a,g),_=R(!1),x=R(""),W=mn(e,["items","options"]),P=R([]),T=R([]),w=I(()=>T.value.concat(P.value).concat(W.value)),$=I(()=>{const{filter:t}=e;if(t)return t;const{labelField:u,valueField:m}=e;return(O,C)=>{if(!C)return!1;const y=C[u];if(typeof y=="string")return et(O,y);const F=C[m];return typeof F=="string"?et(O,F):typeof F=="number"?et(O,String(F)):!1}}),q=I(()=>{if(e.remote)return W.value;{const{value:t}=w,{value:u}=x;return!u.length||!e.filterable?t:Hn(t,$.value,u,e.childrenField)}}),k=I(()=>{const{valueField:t,childrenField:u}=e,m=Wn(t,u);return wn(q.value,m)}),S=I(()=>Kn(w.value,e.valueField,e.childrenField)),N=R(!1),H=ht(Z(e,"show"),N),E=R(null),te=R(null),ee=R(null),{localeRef:de}=Pn("Select"),ie=I(()=>{var t;return(t=e.placeholder)!==null&&t!==void 0?t:de.value.placeholder}),ne=[],h=R(new Map),b=I(()=>{const{fallbackOption:t}=e;if(t===void 0){const{labelField:u,valueField:m}=e;return O=>({[u]:String(O),[m]:O})}return t===!1?!1:u=>Object.assign(t(u),{value:u})});function p(t){const u=e.remote,{value:m}=h,{value:O}=S,{value:C}=b,y=[];return t.forEach(F=>{if(O.has(F))y.push(O.get(F));else if(u&&m.has(F))y.push(m.get(F));else if(C){const G=C(F);G&&y.push(G)}}),y}const B=I(()=>{if(e.multiple){const{value:t}=M;return Array.isArray(t)?p(t):[]}return null}),D=I(()=>{const{value:t}=M;return!e.multiple&&!Array.isArray(t)?t===null?null:p([t])[0]||null:null}),L=yn(e),{mergedSizeRef:V,mergedDisabledRef:j,mergedStatusRef:Q}=L;function Y(t,u){const{onChange:m,"onUpdate:value":O,onUpdateValue:C}=e,{nTriggerFormChange:y,nTriggerFormInput:F}=L;m&&ae(m,t,u),C&&ae(C,t,u),O&&ae(O,t,u),g.value=t,y(),F()}function X(t){const{onBlur:u}=e,{nTriggerFormBlur:m}=L;u&&ae(u,t),m()}function o(){const{onClear:t}=e;t&&ae(t)}function f(t){const{onFocus:u,showOnFocus:m}=e,{nTriggerFormFocus:O}=L;u&&ae(u,t),O(),m&&ce()}function K(t){const{onSearch:u}=e;u&&ae(u,t)}function ue(t){const{onScroll:u}=e;u&&ae(u,t)}function we(){var t;const{remote:u,multiple:m}=e;if(u){const{value:O}=h;if(m){const{valueField:C}=e;(t=B.value)===null||t===void 0||t.forEach(y=>{O.set(y[C],y)})}else{const C=D.value;C&&O.set(C[e.valueField],C)}}}function ye(t){const{onUpdateShow:u,"onUpdate:show":m}=e;u&&ae(u,t),m&&ae(m,t),N.value=t}function ce(){j.value||(ye(!0),N.value=!0,e.filterable&&Ae())}function oe(){ye(!1)}function xe(){x.value="",T.value=ne}const fe=R(!1);function Te(){e.filterable&&(fe.value=!0)}function Oe(){e.filterable&&(fe.value=!1,H.value||xe())}function Me(){j.value||(H.value?e.filterable?Ae():oe():ce())}function ze(t){var u,m;!((m=(u=ee.value)===null||u===void 0?void 0:u.selfRef)===null||m===void 0)&&m.contains(t.relatedTarget)||(_.value=!1,X(t),oe())}function ge(t){f(t),_.value=!0}function be(){_.value=!0}function Pe(t){var u;!((u=E.value)===null||u===void 0)&&u.$el.contains(t.relatedTarget)||(_.value=!1,X(t),oe())}function ke(){var t;(t=E.value)===null||t===void 0||t.focus(),oe()}function Ie(t){var u;H.value&&(!((u=E.value)===null||u===void 0)&&u.$el.contains(On(t))||oe())}function Se(t){if(!Array.isArray(t))return[];if(b.value)return Array.from(t);{const{remote:u}=e,{value:m}=S;if(u){const{value:O}=h;return t.filter(C=>m.has(C)||O.has(C))}else return t.filter(O=>m.has(O))}}function pe(t){J(t.rawNode)}function J(t){if(j.value)return;const{tag:u,remote:m,clearFilterAfterSelect:O,valueField:C}=e;if(u&&!m){const{value:y}=T,F=y[0]||null;if(F){const G=P.value;G.length?G.push(F):P.value=[F],T.value=ne}}if(m&&h.value.set(t[C],t),e.multiple){const y=Se(M.value),F=y.findIndex(G=>G===t[C]);if(~F){if(y.splice(F,1),u&&!m){const G=l(t[C]);~G&&(P.value.splice(G,1),O&&(x.value=""))}}else y.push(t[C]),O&&(x.value="");Y(y,p(y))}else{if(u&&!m){const y=l(t[C]);~y?P.value=[P.value[y]]:P.value=ne}Ee(),oe(),Y(t[C],t)}}function l(t){return P.value.findIndex(m=>m[e.valueField]===t)}function v(t){H.value||ce();const{value:u}=t.target;x.value=u;const{tag:m,remote:O}=e;if(K(u),m&&!O){if(!u){T.value=ne;return}const{onCreate:C}=e,y=C?C(u):{[e.labelField]:u,[e.valueField]:u},{valueField:F,labelField:G}=e;W.value.some(re=>re[F]===y[F]||re[G]===y[G])||P.value.some(re=>re[F]===y[F]||re[G]===y[G])?T.value=ne:T.value=[y]}}function U(t){t.stopPropagation();const{multiple:u}=e;!u&&e.filterable&&oe(),o(),u?Y([],[]):Y(null,null)}function Ue(t){!Be(t,"action")&&!Be(t,"empty")&&!Be(t,"header")&&t.preventDefault()}function qe(t){ue(t)}function $e(t){var u,m,O,C,y;if(!e.keyboard){t.preventDefault();return}switch(t.key){case" ":if(e.filterable)break;t.preventDefault();case"Enter":if(!(!((u=E.value)===null||u===void 0)&&u.isComposing)){if(H.value){const F=(m=ee.value)===null||m===void 0?void 0:m.getPendingTmNode();F?pe(F):e.filterable||(oe(),Ee())}else if(ce(),e.tag&&fe.value){const F=T.value[0];if(F){const G=F[e.valueField],{value:re}=M;e.multiple&&Array.isArray(re)&&re.includes(G)||J(F)}}}t.preventDefault();break;case"ArrowUp":if(t.preventDefault(),e.loading)return;H.value&&((O=ee.value)===null||O===void 0||O.prev());break;case"ArrowDown":if(t.preventDefault(),e.loading)return;H.value?(C=ee.value)===null||C===void 0||C.next():ce();break;case"Escape":H.value&&(Mn(t),oe()),(y=E.value)===null||y===void 0||y.focus();break}}function Ee(){var t;(t=E.value)===null||t===void 0||t.focus()}function Ae(){var t;(t=E.value)===null||t===void 0||t.focusInput()}function Ge(){var t;H.value&&((t=te.value)===null||t===void 0||t.syncPosition())}we(),Fe(Z(e,"options"),we);const Ye={focus:()=>{var t;(t=E.value)===null||t===void 0||t.focus()},focusInput:()=>{var t;(t=E.value)===null||t===void 0||t.focusInput()},blur:()=>{var t;(t=E.value)===null||t===void 0||t.blur()},blurInput:()=>{var t;(t=E.value)===null||t===void 0||t.blurInput()}},Ne=I(()=>{const{self:{menuBoxShadow:t}}=c.value;return{"--n-menu-box-shadow":t}}),he=r?rt("select",void 0,Ne,e):void 0;return Object.assign(Object.assign({},Ye),{mergedStatus:Q,mergedClsPrefix:n,mergedBordered:i,namespace:s,treeMate:k,isMounted:xn(),triggerRef:E,menuRef:ee,pattern:x,uncontrolledShow:N,mergedShow:H,adjustedTo:ot(e),uncontrolledValue:g,mergedValue:M,followerRef:te,localizedPlaceholder:ie,selectedOption:D,selectedOptions:B,mergedSize:V,mergedDisabled:j,focused:_,activeWithoutMenuOpen:fe,inlineThemeDisabled:r,onTriggerInputFocus:Te,onTriggerInputBlur:Oe,handleTriggerOrMenuResize:Ge,handleMenuFocus:be,handleMenuBlur:Pe,handleMenuTabOut:ke,handleTriggerClick:Me,handleToggle:pe,handleDeleteOption:J,handlePatternInput:v,handleClear:U,handleTriggerBlur:ze,handleTriggerFocus:ge,handleKeydown:$e,handleMenuAfterLeave:xe,handleMenuClickOutside:Ie,handleMenuScroll:qe,handleMenuKeydown:$e,handleMenuMousedown:Ue,mergedTheme:c,cssVars:r?void 0:Ne,themeClass:he==null?void 0:he.themeClass,onRender:he==null?void 0:he.onRender})},render(){return d("div",{class:`${this.mergedClsPrefix}-select`},d(Sn,null,{default:()=>[d(Cn,null,{default:()=>d(jn,{ref:"triggerRef",inlineThemeDisabled:this.inlineThemeDisabled,status:this.mergedStatus,inputProps:this.inputProps,clsPrefix:this.mergedClsPrefix,showArrow:this.showArrow,maxTagCount:this.maxTagCount,ellipsisTagPopoverProps:this.ellipsisTagPopoverProps,bordered:this.mergedBordered,active:this.activeWithoutMenuOpen||this.mergedShow,pattern:this.pattern,placeholder:this.localizedPlaceholder,selectedOption:this.selectedOption,selectedOptions:this.selectedOptions,multiple:this.multiple,renderTag:this.renderTag,renderLabel:this.renderLabel,filterable:this.filterable,clearable:this.clearable,disabled:this.mergedDisabled,size:this.mergedSize,theme:this.mergedTheme.peers.InternalSelection,labelField:this.labelField,valueField:this.valueField,themeOverrides:this.mergedTheme.peerOverrides.InternalSelection,loading:this.loading,focused:this.focused,onClick:this.handleTriggerClick,onDeleteOption:this.handleDeleteOption,onPatternInput:this.handlePatternInput,onClear:this.handleClear,onBlur:this.handleTriggerBlur,onFocus:this.handleTriggerFocus,onKeydown:this.handleKeydown,onPatternBlur:this.onTriggerInputBlur,onPatternFocus:this.onTriggerInputFocus,onResize:this.handleTriggerOrMenuResize,ignoreComposition:this.ignoreComposition},{arrow:()=>{var e,n;return[(n=(e=this.$slots).arrow)===null||n===void 0?void 0:n.call(e)]}})}),d(Fn,{ref:"followerRef",show:this.mergedShow,to:this.adjustedTo,teleportDisabled:this.adjustedTo===ot.tdkey,containerClass:this.namespace,width:this.consistentMenuWidth?"target":void 0,minWidth:"target",placement:this.placement},{default:()=>d(xt,{name:"fade-in-scale-up-transition",appear:this.isMounted,onAfterLeave:this.handleMenuAfterLeave},{default:()=>{var e,n,i;return this.mergedShow||this.displayDirective==="show"?((e=this.onRender)===null||e===void 0||e.call(this),Rn(d(Ln,Object.assign({},this.menuProps,{ref:"menuRef",onResize:this.handleTriggerOrMenuResize,inlineThemeDisabled:this.inlineThemeDisabled,virtualScroll:this.consistentMenuWidth&&this.virtualScroll,class:[`${this.mergedClsPrefix}-select-menu`,this.themeClass,(n=this.menuProps)===null||n===void 0?void 0:n.class],clsPrefix:this.mergedClsPrefix,focusable:!0,labelField:this.labelField,valueField:this.valueField,autoPending:!0,nodeProps:this.nodeProps,theme:this.mergedTheme.peers.InternalSelectMenu,themeOverrides:this.mergedTheme.peerOverrides.InternalSelectMenu,treeMate:this.treeMate,multiple:this.multiple,size:"medium",renderOption:this.renderOption,renderLabel:this.renderLabel,value:this.mergedValue,style:[(i=this.menuProps)===null||i===void 0?void 0:i.style,this.cssVars],onToggle:this.handleToggle,onScroll:this.handleMenuScroll,onFocus:this.handleMenuFocus,onBlur:this.handleMenuBlur,onKeydown:this.handleMenuKeydown,onTabOut:this.handleMenuTabOut,onMousedown:this.handleMenuMousedown,show:this.mergedShow,showCheckmark:this.showCheckmark,resetMenuOnOptionsChange:this.resetMenuOnOptionsChange}),{empty:()=>{var s,r;return[(r=(s=this.$slots).empty)===null||r===void 0?void 0:r.call(s)]},header:()=>{var s,r;return[(r=(s=this.$slots).header)===null||r===void 0?void 0:r.call(s)]},action:()=>{var s,r;return[(r=(s=this.$slots).action)===null||r===void 0?void 0:r.call(s)]}}),this.displayDirective==="show"?[[Tn,this.mergedShow],[vt,this.handleMenuClickOutside,void 0,{capture:!0}]]:[[vt,this.handleMenuClickOutside,void 0,{capture:!0}]])):null}})})]}))}});export{An as F,Qn as N,$n as V,jn as a,Ln as b,Wn as c,Je as m,Rt as u};
