package online.ebeinc.allthings140radio;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

public final class RoleConsoleActivity extends Activity {
    public static final String EXTRA_ADMIN = "admin";
    private final Handler main = new Handler(Looper.getMainLooper());
    private SupabaseAuthClient auth;
    private LinearLayout content;
    private LinearLayout reportResults;
    private LinearLayout adminResults;
    private boolean adminView;
    private int dp(float value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state); adminView = getIntent().getBooleanExtra(EXTRA_ADMIN, false); auth = new SupabaseAuthClient(this);
        ScrollView scroll = new ScrollView(this); scroll.setBackgroundColor(Color.rgb(7, 3, 11));
        content = new LinearLayout(this); content.setOrientation(LinearLayout.VERTICAL); content.setPadding(dp(18), dp(28), dp(18), dp(36)); scroll.addView(content); setContentView(scroll);
    }

    @Override protected void onResume() { super.onResume(); verifyRoleAndLoad(); }

    private TextView text(String value, int size, int color) { TextView view=new TextView(this); view.setText(value); view.setTextSize(size); view.setTextColor(color); view.setPadding(0,dp(7),0,dp(7)); return view; }
    private Button button(String label) { Button value=new Button(this); value.setText(label); value.setMinHeight(dp(50)); value.setTextColor(Color.WHITE); value.setBackgroundResource(R.drawable.button_cyber); return value; }
    private LinearLayout card() { LinearLayout card=new LinearLayout(this); card.setOrientation(LinearLayout.VERTICAL); card.setPadding(dp(15),dp(14),dp(15),dp(14)); card.setBackgroundResource(R.drawable.card_background); LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2); p.setMargins(0,0,0,dp(12)); card.setLayoutParams(p); return card; }
    private void message(String value) { Toast.makeText(this,value,Toast.LENGTH_LONG).show(); }

    private void verifyRoleAndLoad() {
        content.removeAllViews(); content.addView(text("CHECKING SERVER AUTHORITY…",14,Color.LTGRAY));
        auth.loadRole((ok,role,status,email,accountClass,accountType,alertAdsPreference,alertAdsEnabled)->main.post(()->{
            boolean moderator="moderator".equals(role)||"admin".equals(role), admin="admin".equals(role);
            if(!ok||!moderator||(adminView&&!admin)){ content.removeAllViews(); content.addView(text("ACCESS DENIED",22,Color.rgb(255,140,170))); content.addView(text("This section requires a current server-authorized "+(adminView?"Admin":"Moderator")+" role.",14,Color.LTGRAY)); return; }
            if(adminView) renderAdmin(); else renderModeration();
        }));
    }

    private void heading(String badge,String title,String subtitle){ content.removeAllViews(); content.addView(text(badge,11,Color.rgb(206,120,255))); content.addView(text(title,25,Color.WHITE)); content.addView(text(subtitle,13,Color.rgb(180,164,190))); }

    private void renderModeration(){ heading("MODERATOR","MODERATION","Pending reports and audited community safety actions"); content.addView(text("PENDING REPORTS",12,Color.rgb(206,120,255))); Button refresh=button("REFRESH QUEUE"); refresh.setOnClickListener(v->{loadReports();loadAudit();}); content.addView(refresh); reportResults=new LinearLayout(this);reportResults.setOrientation(LinearLayout.VERTICAL);content.addView(reportResults);content.addView(text("RECENT ACTIONS",12,Color.rgb(206,120,255)));loadReports();loadAudit(); }
    private void loadReports(){ if(reportResults==null)return;reportResults.removeAllViews();reportResults.addView(text("Loading reports…",13,Color.LTGRAY));auth.rpc("green_room_moderator_reports",json("p_status","pending"),(ok,body,msg)->main.post(()->{ reportResults.removeAllViews();if(!ok){message(msg);return;} try{JSONArray rows=new JSONArray(body); if(rows.length()==0){reportResults.addView(text("No pending reports.",14,Color.LTGRAY));return;} for(int i=0;i<rows.length();i++)reportResults.addView(reportCard(rows.getJSONObject(i)));}catch(Exception e){message("Report data could not be read.");} })); }
    private View reportCard(JSONObject report){ JSONObject snap=report.optJSONObject("message_snapshot"); String name=snap==null?"Reported account":snap.optString("name","Reported account"), message=snap==null?"Evidence unavailable":snap.optString("text","Evidence unavailable"), userId=report.optString("reported_user_id"), reportId=report.optString("id"), messageId=report.optString("message_id"), reason=report.optString("reason","other"),created=report.optString("created_at","Time unavailable"); LinearLayout card=card(); card.addView(text(name,18,Color.WHITE)); card.addView(text(message,14,Color.LTGRAY)); card.addView(text(reason.toUpperCase()+"  •  "+created,11,Color.rgb(190,145,220))); Button delete=button("DELETE MESSAGE"); delete.setOnClickListener(v->confirm("Delete message",name,()->auth.deleteGreenRoomMessage(messageId,userId,reason,(ok,msg)->{if(!ok){main.post(()->message(msg));return;} rpcAction("green_room_resolve_report",payload("p_report_id",reportId,"p_status","resolved","p_action","MESSAGE_DELETE","p_notes","Deleted in Android moderation"));}))); Button resolve=button("RESOLVE REPORT"); resolve.setOnClickListener(v->confirm("Resolve report",name,()->rpcAction("green_room_resolve_report",payload("p_report_id",reportId,"p_status","resolved","p_action","REPORT_RESOLVE","p_notes","Resolved in Android moderation")))); Button dismiss=button("DISMISS REPORT"); dismiss.setOnClickListener(v->confirm("Dismiss report",name,()->rpcAction("green_room_resolve_report",payload("p_report_id",reportId,"p_status","dismissed","p_action","REPORT_DISMISS","p_notes","Dismissed in Android moderation")))); Button ban=button("BAN USER"); ban.setOnClickListener(v->confirm("Ban account",name,()->rpcAction("green_room_set_account_status",payload("p_user_id",userId,"p_status","banned","p_reason","Report "+reportId))));Button unban=button("UNBAN / RESTORE");unban.setOnClickListener(v->confirm("Restore account",name,()->rpcAction("green_room_set_account_status",payload("p_user_id",userId,"p_status","active","p_reason","Moderator restore after report "+reportId)))); card.addView(delete);card.addView(resolve);card.addView(dismiss);card.addView(ban);card.addView(unban);return card; }

    private void renderAdmin(){ heading("ADMIN","ADMIN CONTROLS","Users • Account Types • Moderation • Audit"); content.addView(text("USERS & ACCOUNT TYPES",12,Color.rgb(206,120,255))); EditText query=new EditText(this); query.setHint("Username, email, or UUID"); query.setTextColor(Color.WHITE); query.setHintTextColor(Color.GRAY); query.setMinHeight(dp(54));content.addView(query); Button search=button("SEARCH USERS"); content.addView(search);adminResults=new LinearLayout(this);adminResults.setOrientation(LinearLayout.VERTICAL);content.addView(adminResults);content.addView(text("AUDIT HISTORY",12,Color.rgb(206,120,255)));search.setOnClickListener(v->{String q=query.getText().toString().trim();if(q.length()<2){message("Enter at least two characters.");return;}adminResults.removeAllViews();adminResults.addView(text("Searching…",13,Color.LTGRAY));auth.rpc("admin_lookup_user",json("p_query",q),(ok,body,msg)->main.post(()->{adminResults.removeAllViews();if(!ok){message(msg);return;}try{JSONArray rows=new JSONArray(body);if(rows.length()==0)adminResults.addView(text("No matching users.",14,Color.LTGRAY));for(int i=0;i<rows.length();i++)adminResults.addView(userCard(rows.getJSONObject(i)));}catch(Exception e){message("User results could not be read.");}}));});loadAudit(); }
    private View userCard(JSONObject user){String id=user.optString("user_id"),name=user.optString("username","Profile incomplete"),email=user.optString("email"),role=user.optString("role","user"),status=user.optString("account_status","active"),type=user.optString("account_type","regular");LinearLayout card=card();card.addView(text(name+"  •  "+("partner_sponsor".equals(type)?"PARTNER / SPONSOR":type.toUpperCase()),17,Color.WHITE));card.addView(text(email+"\n"+id+"\n"+status.toUpperCase()+" • ALERT ADS "+(user.optBoolean("alert_ads_enabled",true)?"ON":"OFF"),12,Color.LTGRAY));if(!"admin".equals(role)){String[][] classes={{"regular","REGULAR"},{"plus","TEST PLUS"},{"resident","RESIDENT"},{"partner_sponsor","PARTNER / SPONSOR"}};for(String[] item:classes){Button set=button("SET "+item[1]);set.setOnClickListener(v->confirm("Set account type: "+item[1],name,()->rpcAction("admin_set_account_class",payload("p_user_id",id,"p_account_class",item[0],"p_source","plus".equals(item[0])?"manual_test":"admin","p_reason","Android admin console"))));card.addView(set);}}if("moderator".equals(role)){Button remove=button("REMOVE MODERATOR");remove.setOnClickListener(v->confirm("Remove Moderator",name,()->rpcAction("admin_remove_moderator",payload("p_user_id",id,"p_reason","Android admin console"))));card.addView(remove);}else if(!"admin".equals(role)){Button assign=button("ASSIGN MODERATOR");assign.setOnClickListener(v->confirm("Assign Moderator",name,()->rpcAction("admin_assign_moderator",payload("p_user_id",id,"p_reason","Android admin console"))));card.addView(assign);}if("banned".equals(status)){Button unban=button("UNBAN");unban.setOnClickListener(v->confirm("Unban account",name,()->rpcAction("green_room_set_account_status",payload("p_user_id",id,"p_status","active","p_reason","Android admin console"))));card.addView(unban);}else if(!"admin".equals(role)){Button ban=button("BAN");ban.setOnClickListener(v->confirm("Ban account",name,()->rpcAction("green_room_set_account_status",payload("p_user_id",id,"p_status","banned","p_reason","Android admin console"))));card.addView(ban);}return card;}

    private void loadAudit(){auth.rpc("moderator_recent_actions",json("p_limit",50),(ok,body,msg)->main.post(()->{if(!ok){message(msg);return;}try{JSONArray rows=new JSONArray(body);if(rows.length()==0){content.addView(text("No protected actions recorded.",14,Color.LTGRAY));return;}for(int i=0;i<rows.length();i++){JSONObject action=rows.getJSONObject(i);LinearLayout item=card();String verb=action.optString("action","protected action").replace('_',' ');String target=action.optString("target_username","community");item.addView(text(verb.toUpperCase()+" • "+target,15,Color.WHITE));item.addView(text(action.optString("reason","Server-authorized action"),12,Color.LTGRAY));item.addView(text(action.optString("actor_username","Staff")+" • "+action.optString("created_at",""),10,Color.rgb(170,145,185)));content.addView(item);}}catch(Exception e){message("Audit history could not be read.");}}));}

    private JSONObject json(String key,Object value){try{return new JSONObject().put(key,value);}catch(Exception ignored){return new JSONObject();}}
    private JSONObject payload(Object... pairs){JSONObject value=new JSONObject();try{for(int i=0;i+1<pairs.length;i+=2)value.put(String.valueOf(pairs[i]),pairs[i+1]);}catch(Exception ignored){}return value;}
    private void rpcAction(String name,JSONObject body){auth.rpc(name,body,(ok,json,msg)->main.post(()->{message(ok?"Action completed and audited.":msg);if(ok)verifyRoleAndLoad();}));}
    private void confirm(String action,String target,Runnable yes){new AlertDialog.Builder(this).setTitle(action+"?").setMessage("Target: "+target+"\n\nThis protected action is recorded in the moderation audit log.").setNegativeButton("CANCEL",null).setPositiveButton(action.toUpperCase(),(d,w)->yes.run()).show();}
}
