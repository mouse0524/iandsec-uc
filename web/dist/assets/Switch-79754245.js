import{d7 as se,ey as de,e4 as ce,x as O,y as t,dD as U,c7 as j,c8 as l,c6 as H,z as ue,A as he,B as E,cq as be,r as A,bD as fe,ct as ve,c as V,D as w,cM as K,dq as s,E as ge,ez as N,v as o,dn as m,dy as we,dz as me,cA as P}from"./index-7ec78040.js";function pe(e){const{primaryColor:d,opacityDisabled:f,borderRadius:a,textColor3:r}=e,p="rgba(0, 0, 0, .14)";return Object.assign(Object.assign({},de),{iconColor:r,textColor:"white",loadingColor:d,opacityDisabled:f,railColor:p,railColorActive:d,buttonBoxShadow:"0 1px 4px 0 rgba(0, 0, 0, 0.3), inset 0 0 1px 0 rgba(0, 0, 0, 0.05)",buttonColor:"#FFF",railBorderRadiusSmall:a,railBorderRadiusMedium:a,railBorderRadiusLarge:a,buttonBorderRadiusSmall:a,buttonBorderRadiusMedium:a,buttonBorderRadiusLarge:a,boxShadowFocus:`0 0 0 2px ${ce(d,{alpha:.2})}`})}const ye={name:"Switch",common:se,self:pe},xe=ye,ke=O("switch",`
 height: var(--n-height);
 min-width: var(--n-width);
 vertical-align: middle;
 user-select: none;
 -webkit-user-select: none;
 display: inline-flex;
 outline: none;
 justify-content: center;
 align-items: center;
`,[t("children-placeholder",`
 height: var(--n-rail-height);
 display: flex;
 flex-direction: column;
 overflow: hidden;
 pointer-events: none;
 visibility: hidden;
 `),t("rail-placeholder",`
 display: flex;
 flex-wrap: none;
 `),t("button-placeholder",`
 width: calc(1.75 * var(--n-rail-height));
 height: var(--n-rail-height);
 `),O("base-loading",`
 position: absolute;
 top: 50%;
 left: 50%;
 transform: translateX(-50%) translateY(-50%);
 font-size: calc(var(--n-button-width) - 4px);
 color: var(--n-loading-color);
 transition: color .3s var(--n-bezier);
 `,[U({left:"50%",top:"50%",originalTransform:"translateX(-50%) translateY(-50%)"})]),t("checked, unchecked",`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 box-sizing: border-box;
 position: absolute;
 white-space: nowrap;
 top: 0;
 bottom: 0;
 display: flex;
 align-items: center;
 line-height: 1;
 `),t("checked",`
 right: 0;
 padding-right: calc(1.25 * var(--n-rail-height) - var(--n-offset));
 `),t("unchecked",`
 left: 0;
 justify-content: flex-end;
 padding-left: calc(1.25 * var(--n-rail-height) - var(--n-offset));
 `),j("&:focus",[t("rail",`
 box-shadow: var(--n-box-shadow-focus);
 `)]),l("round",[t("rail","border-radius: calc(var(--n-rail-height) / 2);",[t("button","border-radius: calc(var(--n-button-height) / 2);")])]),H("disabled",[H("icon",[l("rubber-band",[l("pressed",[t("rail",[t("button","max-width: var(--n-button-width-pressed);")])]),t("rail",[j("&:active",[t("button","max-width: var(--n-button-width-pressed);")])]),l("active",[l("pressed",[t("rail",[t("button","left: calc(100% - var(--n-offset) - var(--n-button-width-pressed));")])]),t("rail",[j("&:active",[t("button","left: calc(100% - var(--n-offset) - var(--n-button-width-pressed));")])])])])])]),l("active",[t("rail",[t("button","left: calc(100% - var(--n-button-width) - var(--n-offset))")])]),t("rail",`
 overflow: hidden;
 height: var(--n-rail-height);
 min-width: var(--n-rail-width);
 border-radius: var(--n-rail-border-radius);
 cursor: pointer;
 position: relative;
 transition:
 opacity .3s var(--n-bezier),
 background .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-rail-color);
 `,[t("button-icon",`
 color: var(--n-icon-color);
 transition: color .3s var(--n-bezier);
 font-size: calc(var(--n-button-height) - 4px);
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 display: flex;
 justify-content: center;
 align-items: center;
 line-height: 1;
 `,[U()]),t("button",`
 align-items: center; 
 top: var(--n-offset);
 left: var(--n-offset);
 height: var(--n-button-height);
 width: var(--n-button-width-pressed);
 max-width: var(--n-button-width);
 border-radius: var(--n-button-border-radius);
 background-color: var(--n-button-color);
 box-shadow: var(--n-button-box-shadow);
 box-sizing: border-box;
 cursor: inherit;
 content: "";
 position: absolute;
 transition:
 background-color .3s var(--n-bezier),
 left .3s var(--n-bezier),
 opacity .3s var(--n-bezier),
 max-width .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 `)]),l("active",[t("rail","background-color: var(--n-rail-color-active);")]),l("loading",[t("rail",`
 cursor: wait;
 `)]),l("disabled",[t("rail",`
 cursor: not-allowed;
 opacity: .5;
 `)])]),Ce=Object.assign(Object.assign({},E.props),{size:{type:String,default:"medium"},value:{type:[String,Number,Boolean],default:void 0},loading:Boolean,defaultValue:{type:[String,Number,Boolean],default:!1},disabled:{type:Boolean,default:void 0},round:{type:Boolean,default:!0},"onUpdate:value":[Function,Array],onUpdateValue:[Function,Array],checkedValue:{type:[String,Number,Boolean],default:!0},uncheckedValue:{type:[String,Number,Boolean],default:!1},railStyle:Function,rubberBand:{type:Boolean,default:!0},onChange:[Function,Array]});let B;const Be=ue({name:"Switch",props:Ce,setup(e){B===void 0&&(typeof CSS!="undefined"?typeof CSS.supports!="undefined"?B=CSS.supports("width","max(1px)"):B=!1:B=!0);const{mergedClsPrefixRef:d,inlineThemeDisabled:f}=he(e),a=E("Switch","-switch",ke,xe,e,d),r=be(e),{mergedSizeRef:p,mergedDisabledRef:v}=r,k=A(e.defaultValue),R=fe(e,"value"),g=ve(R,k),C=V(()=>g.value===e.checkedValue),y=A(!1),i=A(!1),c=V(()=>{const{railStyle:n}=e;if(n)return n({focused:i.value,checked:C.value})});function u(n){const{"onUpdate:value":$,onChange:_,onUpdateValue:z}=e,{nTriggerFormInput:F,nTriggerFormChange:D}=r;$&&P($,n),z&&P(z,n),_&&P(_,n),k.value=n,F(),D()}function I(){const{nTriggerFormFocus:n}=r;n()}function q(){const{nTriggerFormBlur:n}=r;n()}function X(){e.loading||v.value||(g.value!==e.checkedValue?u(e.checkedValue):u(e.uncheckedValue))}function Y(){i.value=!0,I()}function G(){i.value=!1,q(),y.value=!1}function J(n){e.loading||v.value||n.key===" "&&(g.value!==e.checkedValue?u(e.checkedValue):u(e.uncheckedValue),y.value=!1)}function Q(n){e.loading||v.value||n.key===" "&&(n.preventDefault(),y.value=!0)}const L=V(()=>{const{value:n}=p,{self:{opacityDisabled:$,railColor:_,railColorActive:z,buttonBoxShadow:F,buttonColor:D,boxShadowFocus:Z,loadingColor:ee,textColor:te,iconColor:ne,[w("buttonHeight",n)]:h,[w("buttonWidth",n)]:ie,[w("buttonWidthPressed",n)]:oe,[w("railHeight",n)]:b,[w("railWidth",n)]:S,[w("railBorderRadius",n)]:ae,[w("buttonBorderRadius",n)]:re},common:{cubicBezierEaseInOut:le}}=a.value;let T,M,W;return B?(T=`calc((${b} - ${h}) / 2)`,M=`max(${b}, ${h})`,W=`max(${S}, calc(${S} + ${h} - ${b}))`):(T=K((s(b)-s(h))/2),M=K(Math.max(s(b),s(h))),W=s(b)>s(h)?S:K(s(S)+s(h)-s(b))),{"--n-bezier":le,"--n-button-border-radius":re,"--n-button-box-shadow":F,"--n-button-color":D,"--n-button-width":ie,"--n-button-width-pressed":oe,"--n-button-height":h,"--n-height":M,"--n-offset":T,"--n-opacity-disabled":$,"--n-rail-border-radius":ae,"--n-rail-color":_,"--n-rail-color-active":z,"--n-rail-height":b,"--n-rail-width":S,"--n-width":W,"--n-box-shadow-focus":Z,"--n-loading-color":ee,"--n-text-color":te,"--n-icon-color":ne}}),x=f?ge("switch",V(()=>p.value[0]),L,e):void 0;return{handleClick:X,handleBlur:G,handleFocus:Y,handleKeyup:J,handleKeydown:Q,mergedRailStyle:c,pressed:y,mergedClsPrefix:d,mergedValue:g,checked:C,mergedDisabled:v,cssVars:f?void 0:L,themeClass:x==null?void 0:x.themeClass,onRender:x==null?void 0:x.onRender}},render(){const{mergedClsPrefix:e,mergedDisabled:d,checked:f,mergedRailStyle:a,onRender:r,$slots:p}=this;r==null||r();const{checked:v,unchecked:k,icon:R,"checked-icon":g,"unchecked-icon":C}=p,y=!(N(R)&&N(g)&&N(C));return o("div",{role:"switch","aria-checked":f,class:[`${e}-switch`,this.themeClass,y&&`${e}-switch--icon`,f&&`${e}-switch--active`,d&&`${e}-switch--disabled`,this.round&&`${e}-switch--round`,this.loading&&`${e}-switch--loading`,this.pressed&&`${e}-switch--pressed`,this.rubberBand&&`${e}-switch--rubber-band`],tabindex:this.mergedDisabled?void 0:0,style:this.cssVars,onClick:this.handleClick,onFocus:this.handleFocus,onBlur:this.handleBlur,onKeyup:this.handleKeyup,onKeydown:this.handleKeydown},o("div",{class:`${e}-switch__rail`,"aria-hidden":"true",style:a},m(v,i=>m(k,c=>i||c?o("div",{"aria-hidden":!0,class:`${e}-switch__children-placeholder`},o("div",{class:`${e}-switch__rail-placeholder`},o("div",{class:`${e}-switch__button-placeholder`}),i),o("div",{class:`${e}-switch__rail-placeholder`},o("div",{class:`${e}-switch__button-placeholder`}),c)):null)),o("div",{class:`${e}-switch__button`},m(R,i=>m(g,c=>m(C,u=>o(we,null,{default:()=>this.loading?o(me,{key:"loading",clsPrefix:e,strokeWidth:20}):this.checked&&(c||i)?o("div",{class:`${e}-switch__button-icon`,key:c?"checked-icon":"icon"},c||i):!this.checked&&(u||i)?o("div",{class:`${e}-switch__button-icon`,key:u?"unchecked-icon":"icon"},u||i):null})))),m(v,i=>i&&o("div",{key:"checked",class:`${e}-switch__checked`},i)),m(k,i=>i&&o("div",{key:"unchecked",class:`${e}-switch__unchecked`},i)))))}});export{Be as _};
